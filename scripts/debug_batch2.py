#!/usr/bin/env python3
"""调试第2批失败原因"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# 创建文档
doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=headers,
    json={"title": "[调试3] 分批"}).json()["data"]["document"]["document_id"]

# convert
with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()
result = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", headers=headers,
    json={"content_type": "markdown", "content": md}).json()["data"]
blocks = result["blocks"]
first_ids = set(result["first_level_block_ids"])
first_blocks = [b for b in blocks if b["block_id"] in first_ids]

def clean(obj):
    if isinstance(obj, dict):
        obj.pop("merge_info", None)
        for v in obj.values(): clean(v)
    elif isinstance(obj, list):
        for item in obj: clean(item)
clean(first_blocks)

print(f"总顶层: {len(first_blocks)}")

# 批次 1: 成功
batch1 = first_blocks[:50]
resp = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    headers=headers, json={"children": batch1, "index": -1})
print(f"批次1: {resp.json()['code']}")

# 查看 batch1 返回的新 block_id 映射
b1_result = resp.json()
b1_mapping = {}  # old_id -> new_id
for child in b1_result.get("data", {}).get("children", []):
    old_id = None
    for orig in batch1:
        if orig.get("block_type") == child.get("block_type"):
            old_id = orig["block_id"]
            break
    if old_id:
        b1_mapping[old_id] = child["block_id"]

# 打印 batch2 中的 parent_id
batch2 = first_blocks[50:]
print(f"\n批次2 ({len(batch2)} blocks):")
print(f"  有 parent_id 的: {sum(1 for b in batch2 if b.get('parent_id'))}")
print(f"  有 children 的: {sum(1 for b in batch2 if b.get('children'))}")

# 检查 batch2 是否引用了 batch1 的 block_id
b1_ids = {b["block_id"] for b in batch1}
refs = set()
for b in batch2:
    if b.get("parent_id") in b1_ids:
        refs.add(b["block_id"])
    for cid in b.get("children", []):
        if cid in b1_ids:
            refs.add(b["block_id"])
print(f"  引用批次1 block_id 的: {len(refs)}")

# 关键：插入后 block_id 会变，需要用返回的新 ID
# 但 convert 返回的是一套自洽的 ID，只要一起发就没问题
# 问题可能是：insert API 不允许在 children 中嵌套已有的 block_id
# 需要用 block_id_to_image_urls？不，那个是空的
# 
# 关键发现：convert 返回的 blocks 里的 children 引用了其他 blocks
# 但这些被引用的 blocks 可能不在 first_level_blocks 中
# 它们在 blocks 数组的非顶层部分
# insert API 需要包含所有被引用的 blocks

# 让我看看 batch2 中 children 引用了哪些不在 batch2 中的 blocks
all_batch2_ids = {b["block_id"] for b in batch2}
missing_refs = set()
for b in batch2:
    for cid in b.get("children", []):
        if cid not in all_batch2_ids and cid not in b1_ids:
            # 这个 child 引用的 block 不在 batch1 或 batch2 中
            missing_refs.add(cid)

print(f"\n批次2 中引用但不在 batch1 或 batch2 中的 blocks: {len(missing_refs)}")
if missing_refs:
    # 找到这些 blocks
    missing_blocks = [b for b in blocks if b["block_id"] in missing_refs]
    print(f"  这些 blocks 的类型: {[b.get('block_type') for b in missing_blocks]}")

# 方案：不拆分，直接全量发送，但超过 50 个限制
# 或者用 batch_create API
print(f"\n--- 尝试 batch_create API ---")
batch_url = f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_create"
body = {"requests": [{"children": first_blocks[:50], "index": -1}]}
print(f"Request body size: {len(json.dumps(body))} bytes")
resp = requests.post(batch_url, headers=headers, json=body)
print(f"batch_create response: {json.dumps(resp.json(), ensure_ascii=False)[:500]}")

print(f"\n📎 https://feishu.cn/docx/{doc_id}")

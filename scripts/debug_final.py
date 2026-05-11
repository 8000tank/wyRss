#!/usr/bin/env python3
"""最终方案：用 batch_create + 全量 blocks"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# 创建文档
doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[最终测试] 全量"}).json()["data"]["document"]["document_id"]
print(f"文档: {doc_id}")

# convert
with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()
result = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", headers=h,
    json={"content_type": "markdown", "content": md}).json()["data"]
all_blocks = result["blocks"]
print(f"convert 返回总 blocks: {len(all_blocks)}")

def clean(obj):
    if isinstance(obj, dict):
        obj.pop("merge_info", None)
        for v in obj.values(): clean(v)
    elif isinstance(obj, list):
        for item in obj: clean(item)
clean(all_blocks)

# 方案1: 全量发送到 children（可能超过 50 限制）
url = f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
print(f"\n--- 方案1: 全量 children insert ---")
print(f"blocks 数量: {len(all_blocks)}")
resp = requests.post(url, headers=h, json={"children": all_blocks, "index": -1})
print(f"status: {resp.status_code}")
# 可能是 400 因为 > 50
try:
    d = resp.json()
    print(f"code: {d.get('code')}, msg: {d.get('msg','')}")
except:
    print(f"raw: {resp.text[:300]}")

# 方案2: 分批，每批 50，但包含被引用的非顶层 blocks
print(f"\n--- 方案2: 分批 50（智能分批）---")
# 飞书的 insert children API 实际上是递归的 - 你传一个顶层 block，
# 它的 children 字段里引用的 sub-blocks 会被自动处理
# 所以关键是只传 first_level_blocks，但每个 block 内部要有完整的 children 引用

first_ids = set(result["first_level_block_ids"])
first_blocks = [b for b in all_blocks if b["block_id"] in first_ids]
print(f"顶层 blocks: {len(first_blocks)}")

# 按每批 50 分
BATCH = 50
total = 0
for i in range(0, len(first_blocks), BATCH):
    batch = first_blocks[i:i+BATCH]
    resp = requests.post(url, headers=h, json={"children": batch, "index": -1})
    try:
        d = resp.json()
        if d.get("code") == 0:
            ins = len(d.get("data", {}).get("children", batch))
            total += ins
            print(f"  批次{i//BATCH+1}: ✅ {ins} blocks")
        else:
            print(f"  批次{i//BATCH+1}: ❌ code={d.get('code')} msg={d.get('msg','')[:100]}")
            # 打印第一个失败 block 的详情
            if d.get("error", {}).get("field_violations"):
                for fv in d["error"]["field_violations"]:
                    print(f"    field={fv.get('field')} desc={fv.get('description')}")
            # 尝试二分法找出哪个 block 有问题
            if len(batch) > 1:
                mid = len(batch) // 2
                for sub_name, sub_batch in [("前半", batch[:mid]), ("后半", batch[mid:])]:
                    resp2 = requests.post(url, headers=h, json={"children": sub_batch, "index": -1})
                    try:
                        d2 = resp2.json()
                        if d2.get("code") == 0:
                            print(f"    {sub_name}({len(sub_batch)}): ✅")
                            total += len(sub_batch)
                        else:
                            print(f"    {sub_name}({len(sub_batch)}): ❌")
                    except:
                        print(f"    {sub_name}({len(sub_batch)}): parse error")
    except Exception as e:
        print(f"  批次{i//BATCH+1}: ❌ {e}")

print(f"\n总计插入: {total}")
print(f"📎 https://feishu.cn/docx/{doc_id}")

#!/usr/bin/env python3
"""调试批量 insert"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# 创建文档
doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=headers,
    json={"title": "[调试2] 批量"}).json()["data"]["document"]["document_id"]
print(f"文档: {doc_id}")

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

print(f"待插入: {len(first_blocks)} blocks")

# 分批测试 - 先试 10 个
for batch_size in [10, 50]:
    batch = first_blocks[:batch_size]
    url = f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    body = {"children": batch, "index": -1}
    resp = requests.post(url, headers=headers, json=body)
    print(f"\n批量 {batch_size}: status={resp.status_code}")
    d = resp.json()
    print(f"  code={d.get('code')}, msg={d.get('msg','')}")
    if d.get("code") != 0:
        print(f"  错误详情: {json.dumps(d, ensure_ascii=False)[:500]}")
    else:
        inserted = d.get("data", {}).get("children", [])
        print(f"  成功插入 {len(inserted)} blocks")

# 测试全部
url = f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
body = {"children": first_blocks, "index": -1}
print(f"\n--- 全部 {len(first_blocks)} blocks ---")
print(f"Request size: {len(json.dumps(body))} bytes")
resp = requests.post(url, headers=headers, json=body)
print(f"Status: {resp.status_code}")
d = resp.json()
print(f"code={d.get('code')}, msg={d.get('msg','')}")
if d.get("code") != 0:
    print(f"错误: {json.dumps(d, ensure_ascii=False)[:800]}")
else:
    inserted = d.get("data", {}).get("children", [])
    print(f"成功插入 {len(inserted)} blocks")

print(f"\n📎 https://feishu.cn/docx/{doc_id}")

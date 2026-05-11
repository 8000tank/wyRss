#!/usr/bin/env python3
"""调试 insert blocks API"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

def get_token():
    resp = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
                         json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]

token = get_token()

# 创建文档
resp = requests.post(f"{BASE_URL}/docx/v1/documents",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"title": "[调试] 测试"})
doc_id = resp.json()["data"]["document"]["document_id"]
print(f"文档: {doc_id}")

# 读取 markdown
with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()

# convert
resp = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    json={"content_type": "markdown", "content": md})
result = resp.json()["data"]
blocks = result["blocks"]
first_ids = set(result["first_level_block_ids"])
first_blocks = [b for b in blocks if b["block_id"] in first_ids]
print(f"顶层 blocks: {len(first_blocks)}")

# 清理 merge_info
def clean(obj):
    if isinstance(obj, dict):
        obj.pop("merge_info", None)
        for v in obj.values():
            clean(v)
    elif isinstance(obj, list):
        for item in obj:
            clean(item)
clean(first_blocks)

# 尝试普通 insert - 只发第一个 block
print("\n--- 尝试 insert 单个 block ---")
url = f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
body = {"children": [first_blocks[0]], "index": -1}
print(f"URL: {url}")
print(f"Block type: {first_blocks[0].get('block_type')}")
print(f"Request body (前 500): {json.dumps(body, ensure_ascii=False)[:500]}")
resp = requests.post(url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    json=body)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:1000]}")

# 打印完整的请求
print("\n--- 完整第一个 block ---")
print(json.dumps(first_blocks[0], indent=2, ensure_ascii=False))

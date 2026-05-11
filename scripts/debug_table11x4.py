#!/usr/bin/env python3
"""调试：单独插入失败的 11×4 表格"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()
result = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", headers=h,
    json={"content_type": "markdown", "content": md}).json()["data"]
block_map = {b["block_id"]: b for b in result["blocks"]}
first_blocks = [block_map[bid] for bid in result["first_level_block_ids"]]

# Block index 4 是那个 11×4 的表格
problem_block = first_blocks[4]
print(f"Block[4] type: {problem_block.get('block_type')}")
prop = problem_block.get("table", {}).get("property", {})
print(f"Size: {prop.get('row_size')}x{prop.get('column_size')}")

# 清理
def clean(obj):
    if isinstance(obj, dict):
        obj.pop("merge_info", None)
        for v in obj.values(): clean(v)
    elif isinstance(obj, list):
        for item in obj: clean(item)
clean(problem_block)

# 打印完整 block
print(json.dumps(problem_block, indent=2, ensure_ascii=False)[:2000])

# 单独创建文档并插入
doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] 单独表格"}).json()["data"]["document"]["document_id"]

r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    headers=h, json={"children": [problem_block], "index": -1})
d = r.json()
print(f"\n单独插入: code={d.get('code')} msg={d.get('msg','')[:200]}")
if d.get("code") != 0:
    print(json.dumps(d.get("error", {}), indent=2, ensure_ascii=False))

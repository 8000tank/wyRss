#!/usr/bin/env python3
"""调试：去掉 children 字段后单独插入 11×4 表格"""
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

problem_block = first_blocks[4]

# 测试1: 去掉 children 字段
block_v1 = json.loads(json.dumps(problem_block))
block_v1.pop("children", None)
block_v1.pop("merge_info", None)

doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] 去children"}).json()["data"]["document"]["document_id"]
r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    headers=h, json={"children": [block_v1], "index": -1})
d = r.json()
print(f"去掉 children: code={d.get('code')} msg={d.get('msg','')[:100]}")
if d.get("code") == 0:
    print("✅ 成功！")

# 测试2: 清空 children 列表
block_v2 = json.loads(json.dumps(problem_block))
block_v2["children"] = []
block_v2.pop("merge_info", None)

doc_id2 = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] 空children"}).json()["data"]["document"]["document_id"]
r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id2}/blocks/{doc_id2}/children",
    headers=h, json={"children": [block_v2], "index": -1})
d = r.json()
print(f"空 children 列表: code={d.get('code')} msg={d.get('msg','')[:100]}")
if d.get("code") == 0:
    print("✅ 成功！")

# 测试3: 检查成功的 5×3 表格 children 格式
for i, bid in enumerate(result["first_level_block_ids"]):
    b = block_map[bid]
    if b.get("block_type") == 31:
        prop = b.get("table", {}).get("property", {})
        if prop.get("row_size") == 5 and prop.get("column_size") == 3:
            print(f"\n5×3 表格 children 样本: {b.get('children', [])[:3]}")
            print(f"5×3 表格 cells: {b.get('table', {}).get('cells', [])[:3]}")
            break

print(f"\n11×4 表格 children 样本: {problem_block.get('children', [])[:3]}")
print(f"11×4 表格 cells: {problem_block.get('table', {}).get('cells', [])[:3]}")

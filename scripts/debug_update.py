#!/usr/bin/env python3
"""调试 update_block API 的正确格式"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# 创建测试文档
doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] update block"}).json()["data"]["document"]["document_id"]
print(f"文档: {doc_id}")

# 插入一个简单的 text block
r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    headers=h, json={"children": [{
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": "hello world"}}], "style": {}}
    }], "index": -1})
d = r.json()
print(f"insert text: code={d.get('code')}")
text_block_id = d["data"]["children"][0]["block_id"]
print(f"text_block_id: {text_block_id}")

# 读取这个 block 看看结构
r = requests.get(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{text_block_id}", headers=h)
d = r.json()
print(f"\n读取 text block:")
print(json.dumps(d.get("data", {}).get("block", {}), indent=2, ensure_ascii=False))

# 尝试 update - 方式1: 只传 text
r = requests.patch(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{text_block_id}",
    headers=h, json={
        "text": {"elements": [{"text_run": {"content": "updated!"}}], "style": {}}
    })
d = r.json()
print(f"\nupdate 方式1 (只传 text): code={d.get('code')} msg={d.get('msg','')}")

# 读取更新后的内容
r = requests.get(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{text_block_id}", headers=h)
d = r.json()
content = ""
for el in d.get("data", {}).get("block", {}).get("text", {}).get("elements", []):
    content += el.get("text_run", {}).get("content", "")
print(f"更新后内容: '{content}'")

# 创建一个带表格的文档
doc2_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] table"}).json()["data"]["document"]["document_id"]

# 插入一个 table (用 create_table API)
r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc2_id}/blocks/{doc2_id}/children",
    headers=h, json={"children": [{
        "block_type": 31,
        "table": {
            "property": {
                "row_size": 2,
                "column_size": 2,
                "column_width": [200, 200],
            }
        }
    }], "index": -1})
d = r.json()
print(f"\ninsert table: code={d.get('code')}")
table_block = d["data"]["children"][0]
table_id = table_block["block_id"]
cell_ids = table_block["table"]["cells"]
print(f"table_id: {table_id}")
print(f"cell_ids: {cell_ids}")

# 读取 table 的子 blocks
time.sleep(0.5)
r = requests.get(f"{BASE_URL}/docx/v1/documents/{doc2_id}/blocks/{table_id}/children",
    headers=h, params={"page_size": 100})
d = r.json()
items = d["data"]["items"]
print(f"\ntable children ({len(items)} blocks):")
for item in items:
    bt = item.get("block_type")
    bid = item.get("block_id")
    if bt == 32:  # TableCell
        children = item.get("children", [])
        print(f"  Cell {bid}: children={children}")
        # 读取 cell 的 text block
        if children:
            r2 = requests.get(f"{BASE_URL}/docx/v1/documents/{doc2_id}/blocks/{children[0]}", headers=h)
            d2 = r2.json()
            tb = d2.get("data", {}).get("block", {})
            elems = tb.get("text", {}).get("elements", [])
            txt = "".join(e.get("text_run", {}).get("content", "") for e in elems)
            print(f"    Text block: '{txt}'")
            print(f"    Full block: {json.dumps(tb, ensure_ascii=False)[:200]}")

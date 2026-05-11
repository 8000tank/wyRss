#!/usr/bin/env python3
"""测试：去掉 merge_info 后插入 11×4 表格"""
import requests, json

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

block = json.loads(json.dumps(first_blocks[4]))  # 11×4 table

# 去掉 merge_info
tests = [
    ("去掉 merge_info", lambda b: b["table"]["property"].pop("merge_info", None)),
    ("去掉 children + merge_info", lambda b: (b.pop("children", None), b["table"]["property"].pop("merge_info", None))),
    ("最小: 只保留 row/col/column_width", lambda b: b["table"]["property"].__setitem__("property", {
        "row_size": b["table"]["property"]["row_size"],
        "column_size": b["table"]["property"]["column_size"],
        "column_width": b["table"]["property"]["column_width"],
    })),
]

# Actually test the simple cases
for name, fn in [
    ("去掉 merge_info", "merge_info"),
    ("去掉 column_width", "column_width"),
    ("只保留 row_size + column_size", "both"),
]:
    b = json.loads(json.dumps(first_blocks[4]))
    b.pop("merge_info", None)  # top-level merge_info
    
    if fn == "merge_info":
        b["table"]["property"].pop("merge_info", None)
    elif fn == "column_width":
        b["table"]["property"].pop("column_width", None)
    elif fn == "both":
        b["table"]["property"] = {
            "row_size": b["table"]["property"]["row_size"],
            "column_size": b["table"]["property"]["column_size"],
        }
    
    doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
        json={"title": f"[调试] {name}"}).json()["data"]["document"]["document_id"]
    r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
        headers=h, json={"children": [b], "index": -1})
    d = r.json()
    print(f"{name}: code={d.get('code')} msg={d.get('msg','')[:100]}")
    if d.get("code") == 0:
        print(f"  ✅ 成功! 📎 https://feishu.cn/docx/{doc_id}")

#!/usr/bin/env python3
"""测试：用飞书原生 API 直接创建 11×4 表格（不用 convert 的 block）"""
import requests, json

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] 原生创建表格"}).json()["data"]["document"]["document_id"]

# 方式1: 手动构造一个简单的 11×4 表格 block
simple_table = {
    "block_type": 31,
    "table": {
        "property": {
            "row_size": 11,
            "column_size": 4,
            "column_width": [183, 183, 183, 183],
            "merge_info": [{"col_span": 1, "row_span": 1}] * 44,
        },
        "cells": []  # 空的，让飞书自动生成
    }
}

r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    headers=h, json={"children": [simple_table], "index": -1})
d = r.json()
print(f"方式1 (原生 block, empty cells): code={d.get('code')} msg={d.get('msg','')[:100]}")
if d.get("code") == 0:
    print(f"  ✅ 成功! 📎 https://feishu.cn/docx/{doc_id}")

# 方式2: 用 convert API 的 block 但去掉 cells
with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()
result = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", headers=h,
    json={"content_type": "markdown", "content": md}).json()["data"]
block_map = {b["block_id"]: b for b in result["blocks"]]
first_blocks = [block_map[bid] for bid in result["first_level_block_ids"]]
block = json.loads(json.dumps(first_blocks[4]))

doc_id2 = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] convert block no cells"}).json()["data"]["document"]["document_id"]

block["table"]["cells"] = []  # 清空 cells

r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id2}/blocks/{doc_id2}/children",
    headers=h, json={"children": [block], "index": -1})
d = r.json()
print(f"方式2 (convert block, empty cells): code={d.get('code')} msg={d.get('msg','')[:100]}")
if d.get("code") == 0:
    print(f"  ✅ 成功! 📎 https://feishu.cn/docx/{doc_id2}")

# 方式3: convert block 去掉 children
doc_id3 = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] no children"}).json()["data"]["document"]["document_id"]
block3 = json.loads(json.dumps(first_blocks[4]))
block3.pop("children", None)
block3.pop("merge_info", None)

r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id3}/blocks/{doc_id3}/children",
    headers=h, json={"children": [block3], "index": -1})
d = r.json()
print(f"方式3 (no children, no merge_info): code={d.get('code')} msg={d.get('msg','')[:100]}")
if d.get("code") == 0:
    print(f"  ✅ 成功! 📎 https://feishu.cn/docx/{doc_id3}")

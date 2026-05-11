#!/usr/bin/env python3
"""检查 convert API 返回的表头 cell 是否有特殊样式"""
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

# 找第一个 5×3 表格，对比第1行（表头）和第2行（数据行）的 cell 差异
for bid in result["first_level_block_ids"]:
    b = block_map[bid]
    if b.get("block_type") != 31:
        continue
    prop = b.get("table", {}).get("property", {})
    if prop.get("row_size") == 5 and prop.get("column_size") == 3:
        cells = b.get("table", {}).get("cells", [])
        print(f"=== 5×3 表格 cell 对比 ===")
        # 第1行: header cells (index 0,1,2)
        # 第2行: data cells (index 3,4,5)
        for label, indices in [("表头", [0,1,2]), ("数据", [3,4,5])]:
            for ci in indices:
                cid = cells[ci]
                cell = block_map.get(cid)
                if not cell:
                    continue
                # 获取 cell 的完整结构（排除 text content）
                cell_info = {
                    "block_id": cid,
                    "block_type": cell.get("block_type"),
                    "table_cell_property": cell.get("table_cell", {}).get("property", {}),
                    # 检查是否有 column_header 或类似字段
                    "keys": list(cell.keys()),
                }
                # 也获取 text block 的 style
                children = cell.get("children", [])
                if children:
                    tb = block_map.get(children[0])
                    if tb:
                        text_style = tb.get("text", {}).get("style", {})
                        elements = tb.get("text", {}).get("elements", [])
                        elem_style = elements[0].get("text_run", {}).get("text_element_style", {}) if elements else {}
                        content = "".join(e.get("text_run", {}).get("content", "") for e in elements)
                        cell_info["text_style"] = text_style
                        cell_info["elem_style"] = elem_style
                        cell_info["content"] = content[:20]
                print(f"\n  {label} cell[{ci}]:")
                print(f"    {json.dumps(cell_info, indent=4, ensure_ascii=False)}")
        break

# 也看看飞书已创建文档中的 cell 结构
DOC_ID = "D3XQdhqePoZkwXxUNVqcZKSYngg"
doc_children = requests.get(
    f"{BASE_URL}/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children",
    headers=h, params={"page_size": 500}).json()["data"]["items"]

# 找第一个 5×3 的 table
for item in doc_children:
    if item.get("block_type") != 31:
        continue
    dt_prop = item.get("table", {}).get("property", {})
    if dt_prop.get("row_size") == 5 and dt_prop.get("column_size") == 3:
        table_id = item["block_id"]
        doc_cell_ids = item.get("table", {}).get("cells", [])
        
        # 获取 table children
        time.sleep(0.3)
        cell_items = requests.get(
            f"{BASE_URL}/docx/v1/documents/{DOC_ID}/blocks/{table_id}/children",
            headers=h, params={"page_size": 500}).json()["data"]["items"]
        
        print(f"\n\n=== 飞书文档中 5×3 表格 cell 对比 ===")
        for label, indices in [("表头", [0,1,2]), ("数据", [3,4,5])]:
            for ci in indices:
                cid = doc_cell_ids[ci]
                cell = next((c for c in cell_items if c["block_id"] == cid), None)
                if not cell:
                    continue
                # 获取 text block
                children = cell.get("children", [])
                text_content = ""
                text_style = {}
                if children:
                    time.sleep(0.2)
                    tb = requests.get(
                        f"{BASE_URL}/docx/v1/documents/{DOC_ID}/blocks/{children[0]}",
                        headers=h).json()["data"]["block"]
                    text_style = tb.get("text", {}).get("style", {})
                    elems = tb.get("text", {}).get("elements", [])
                    text_content = "".join(e.get("text_run", {}).get("content", "") for e in elems)
                
                cell_info = {
                    "block_type": cell.get("block_type"),
                    "table_cell_property": cell.get("table_cell", {}).get("property", {}),
                    "text_style": text_style,
                    "content": text_content[:20],
                    "keys": list(cell.keys()),
                }
                print(f"\n  {label} cell[{ci}]:")
                print(f"    {json.dumps(cell_info, indent=4, ensure_ascii=False)}")
        break

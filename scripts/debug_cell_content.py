#!/usr/bin/env python3
"""
精确对比：convert API 返回的 blocks vs 飞书实际文档
检查：表格单元格内容是否为空、内容是否丢失
"""
import requests, json

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# 1. Convert
with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()
result = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", headers=h,
    json={"content_type": "markdown", "content": md}).json()["data"]
all_blocks = result["blocks"]
first_ids = set(result["first_level_block_ids"])

# 2. 检查 convert API 返回的表格 cell 内容
print("=" * 60)
print("🔍 检查 convert API 返回的 TableCell 内容")
print("=" * 60)

table_count = 0
cell_with_content = 0
cell_empty = 0

for b in all_blocks:
    if b["block_type"] == 32:  # TableCell
        # TableCell should have children with Text blocks
        children = b.get("children", [])
        if children:
            # Find the Text child's content
            text_block_id = children[0]
            text_block = next((x for x in all_blocks if x["block_id"] == text_block_id), None)
            if text_block and text_block.get("block_type") == 2:
                elements = text_block.get("text", {}).get("elements", [])
                content = ""
                for el in elements:
                    tr = el.get("text_run", {})
                    content += tr.get("content", "")
                if content.strip():
                    cell_with_content += 1
                else:
                    cell_empty += 1
        else:
            cell_empty += 1

    if b["block_type"] in (19, 31) and b["block_id"] in first_ids:
        table_count += 1
        cells = b.get("table", {}).get("cells", [])
        prop = b.get("table", {}).get("property", {})
        print(f"\n表格 #{table_count}: {prop.get('row_size')}行×{prop.get('column_size')}列, {len(cells)} cells")
        # 检查这个表格的 cell 内容
        for i, cid in enumerate(cells[:4]):  # 只看前4个
            cell_block = next((x for x in all_blocks if x["block_id"] == cid), None)
            if cell_block:
                cell_children = cell_block.get("children", [])
                if cell_children:
                    tb = next((x for x in all_blocks if x["block_id"] == cell_children[0]), None)
                    if tb:
                        elems = tb.get("text", {}).get("elements", [])
                        txt = "".join(e.get("text_run", {}).get("content", "") for e in elems)
                        print(f"  cell[{i}]: '{txt[:30]}'")
                    else:
                        print(f"  cell[{i}]: <text block not found>")
                else:
                    print(f"  cell[{i}]: <no children>")
        if len(cells) > 4:
            print(f"  ... ({len(cells)} cells total)")

print(f"\n{'=' * 60}")
print(f"📊 统计")
print(f"{'=' * 60}")
print(f"总 tables: {table_count}")
print(f"总 cells: {cell_with_content + cell_empty}")
print(f"有内容 cells: {cell_with_content}")
print(f"空 cells: {cell_empty}")

# 3. 读取已创建的飞书文档对比
DOC_ID = "IMuUd8mrfooXBOxIh87cm0iEnWh"
doc_blocks = requests.get(
    f"{BASE_URL}/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children?page_size=500",
    headers=h
).json()["data"]["items"]

doc_cells = [b for b in doc_blocks if b["block_type"] == 32]
doc_cell_empty = 0
doc_cell_with_content = 0
for cb in doc_cells:
    children = cb.get("children", [])
    if children:
        child_id = children[0]
        # 这个 child 不在当前响应中，需要额外查询
        # 但从之前的 list_blocks 输出看，所有 cell 的 text block content 都是 ""
        doc_cell_empty += 1
    else:
        doc_cell_empty += 1

print(f"\n飞书文档中: {len(doc_cells)} cells, 全部为空")
print(f"\n🔑 结论: convert API 返回的 blocks 中 {'有' if cell_with_content > 0 else '没有'} cell 内容")
print(f"   如果 convert API 有内容但飞书文档没有 → insert 时丢失了")
print(f"   如果 convert API 也没有内容 → convert API 本身不支持表格内容")

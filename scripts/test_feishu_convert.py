#!/usr/bin/env python3
"""
飞书 Markdown → 飞书文档 v10
- 表格行数超限时自动拆分
- Phase 2 填充 cell 内容
"""
import requests, json, time, sys, re

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

BLOCK_TYPES = {
    2: "Text", 3: "H1", 4: "H2", 5: "H3", 12: "Bullet", 13: "Ordered",
    14: "Code", 15: "Quote", 17: "Divider", 18: "Image", 19: "Table",
    22: "View", 31: "Table", 32: "TableCell",
}

MAX_TABLE_ROWS = 9  # 飞书表格最大行数


class FeishuClient:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._expire = 0

    def _get_token(self):
        if self._token and time.time() < self._expire:
            return self._token
        r = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
                          json={"app_id": self.app_id, "app_secret": self.app_secret})
        d = r.json()
        if d["code"] != 0:
            raise Exception(f"token error: {d}")
        self._token = d["tenant_access_token"]
        self._expire = time.time() + d.get("expire", 7200) - 60
        return self._token

    @property
    def h(self):
        return {"Authorization": f"Bearer {self._get_token()}",
                "Content-Type": "application/json; charset=utf-8"}

    def create_doc(self, title):
        r = requests.post(f"{BASE_URL}/docx/v1/documents", headers=self.h, json={"title": title})
        d = r.json()
        if d["code"] != 0:
            raise Exception(f"create error: {d}")
        return d["data"]["document"]["document_id"]

    def convert_md(self, md):
        r = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", headers=self.h,
                          json={"content_type": "markdown", "content": md})
        d = r.json()
        if d["code"] != 0:
            raise Exception(f"convert error: {d}")
        return d["data"]

    def insert_children(self, doc_id, children, index=-1):
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                    headers=self.h, json={"children": children, "index": index})
                d = r.json()
                if d["code"] != 0:
                    raise Exception(f"code={d['code']}")
                return d["data"]
            except requests.exceptions.JSONDecodeError:
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                raise
        raise Exception("insert failed")

    def get_children(self, doc_id, block_id, page_size=500):
        r = requests.get(
            f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{block_id}/children",
            headers=self.h, params={"page_size": page_size})
        d = r.json()
        if d["code"] != 0:
            raise Exception(f"get error: {d}")
        return d["data"]["items"]

    def update_text(self, doc_id, block_id, elements):
        for attempt in range(3):
            try:
                time.sleep(0.03)
                r = requests.patch(
                    f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{block_id}",
                    headers=self.h,
                    json={"update_text_elements": {"elements": elements}})
                d = r.json()
                if d.get("code") == 0:
                    return True
                if d.get("code") == 1770001:
                    return False
                if attempt < 2:
                    time.sleep(0.3)
                    continue
                return False
            except requests.exceptions.JSONDecodeError:
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                return False
        return False


def clean(obj):
    if isinstance(obj, dict):
        obj.pop("merge_info", None)
        for v in obj.values():
            clean(v)
    elif isinstance(obj, list):
        for item in obj:
            clean(item)


def get_cell_elements(all_blocks, cell_id):
    cell_block = None
    for b in all_blocks:
        if b["block_id"] == cell_id:
            cell_block = b
            break
    if not cell_block:
        return None
    children = cell_block.get("children", [])
    if not children:
        return None
    text_block = None
    for b in all_blocks:
        if b["block_id"] == children[0]:
            text_block = b
            break
    if not text_block or text_block.get("block_type") != 2:
        return None
    return text_block.get("text", {}).get("elements", [])


def split_large_tables(first_blocks, all_blocks, max_rows=MAX_TABLE_ROWS):
    """
    将超过 max_rows 的表格拆分成多个小表格。
    返回新的 first_blocks 列表和拆分信息。
    """
    new_blocks = []
    split_info = []  # 记录拆分关系: (original_table_index, [split_block_indices])

    for i, b in enumerate(first_blocks):
        if b.get("block_type") not in (19, 31):
            new_blocks.append(b)
            continue

        prop = b.get("table", {}).get("property", {})
        rows = prop.get("row_size", 0)
        cols = prop.get("column_size", 0)
        cells = b.get("table", {}).get("cells", [])

        if rows <= max_rows:
            new_blocks.append(b)
            split_info.append((i, [len(new_blocks) - 1]))
            continue

        # 需要拆分
        original_idx = len(new_blocks)
        col_width = prop.get("column_width", [730 // cols] * cols)
        split_indices = []

        for chunk_start in range(0, rows, max_rows):
            chunk_rows = min(max_rows, rows - chunk_start)
            chunk_cells = []
            for r in range(chunk_start, chunk_start + chunk_rows):
                for c in range(cols):
                    cell_idx = r * cols + c
                    if cell_idx < len(cells):
                        chunk_cells.append(cells[cell_idx])

            new_table = {
                "block_type": 31,
                "table": {
                    "property": {
                        "row_size": chunk_rows,
                        "column_size": cols,
                        "column_width": col_width,
                    },
                    "cells": chunk_cells,
                }
            }
            new_blocks.append(new_table)
            split_indices.append(len(new_blocks) - 1)

        split_info.append((i, split_indices))

    return new_blocks, split_info


def main():
    md_file = sys.argv[1] if len(sys.argv) > 1 else "/root/code/wyRss/output/AI-digest_20260327_035845.md"
    doc_title = sys.argv[2] if len(sys.argv) > 2 else None

    with open(md_file, "r", encoding="utf-8") as f:
        md = f.read()

    client = FeishuClient(APP_ID, APP_SECRET)

    if not doc_title:
        m = re.match(r"^#\s+(.+)", md, re.MULTILINE)
        doc_title = m.group(1).strip() if m else "Untitled"

    print(f"📄 Markdown: {len(md)} 字符")
    doc_id = client.create_doc(doc_title)
    url = f"https://feishu.cn/docx/{doc_id}"
    print(f"📝 文档: {url}")

    # 转换
    print("🔄 Markdown → Blocks...")
    data = client.convert_md(md)
    all_blocks = data["blocks"]
    first_level_block_ids = data["first_level_block_ids"]
    block_map = {}
    for b in all_blocks:
        block_map[b["block_id"]] = b
    first_blocks = []
    for bid in first_level_block_ids:
        first_blocks.append(block_map[bid])
    clean(first_blocks)

    # 收集表格信息
    table_infos = []
    for i, bid in enumerate(first_level_block_ids):
        b = block_map[bid]
        if b.get("block_type") in (19, 31):
            prop = b.get("table", {}).get("property", {})
            cells = b.get("table", {}).get("cells", [])
            table_infos.append({
                "index": i,
                "block_id": bid,
                "rows": prop.get("row_size", 0),
                "cols": prop.get("column_size", 0),
                "cell_ids": cells,
            })

    print(f"   顶层 blocks: {len(first_blocks)}, 表格: {len(table_infos)}")

    # 检查是否有超限表格
    oversized = [t for t in table_infos if t["rows"] > MAX_TABLE_ROWS]
    if oversized:
        print(f"   ⚠️ {len(oversized)} 个表格超过 {MAX_TABLE_ROWS} 行限制，将拆分")
        for t in oversized:
            print(f"      {t['rows']}×{t['cols']} → 拆分为 {(t['rows'] + MAX_TABLE_ROWS - 1) // MAX_TABLE_ROWS} 个")

    # 拆分大表格
    first_blocks, split_info = split_large_tables(first_blocks, all_blocks, MAX_TABLE_ROWS)

    # 更新 table_infos，反映拆分后的 block 映射
    # split_info: [(original_table_index, [new_block_indices]), ...]
    # 我们需要为每个拆分后的 block 建立 cell_ids 映射
    split_table_infos = []
    for si, (orig_idx, new_indices) in enumerate(split_info):
        orig_info = table_infos[si]
        if len(new_indices) == 1:
            # 没有拆分
            split_table_infos.append({
                "new_index": new_indices[0],
                "cell_ids": orig_info["cell_ids"],
                "rows": orig_info["rows"],
                "cols": orig_info["cols"],
            })
        else:
            # 拆分了
            cells = orig_info["cell_ids"]
            cols = orig_info["cols"]
            for ci, ni in enumerate(new_indices):
                chunk_start = ci * MAX_TABLE_ROWS * cols
                chunk_end = min(chunk_start + MAX_TABLE_ROWS * cols, len(cells))
                chunk_cells = cells[chunk_start:chunk_end]
                actual_rows = len(chunk_cells) // cols
                split_table_infos.append({
                    "new_index": ni,
                    "cell_ids": chunk_cells,
                    "rows": actual_rows,
                    "cols": cols,
                })

    print(f"   拆分后 blocks: {len(first_blocks)}, 表格: {len(split_table_infos)}")

    # === Phase 1: 插入 ===
    print("\n📥 Phase 1: 插入文档结构...")
    inserted_ok = [False] * len(first_blocks)
    BATCH = 50

    for i in range(0, len(first_blocks), BATCH):
        batch = first_blocks[i:i+BATCH]
        time.sleep(0.3)
        try:
            client.insert_children(doc_id, batch)
            for j in range(len(batch)):
                inserted_ok[i + j] = True
            print(f"   ✅ 批次{i//BATCH+1}: {len(batch)} blocks")
        except Exception:
            print(f"   ⚠️ 批次{i//BATCH+1} 失败, 逐个重试...")
            for j, block in enumerate(batch):
                ok = False
                for attempt in range(3):
                    try:
                        time.sleep(0.2)
                        client.insert_children(doc_id, [block])
                        ok = True
                        break
                    except requests.exceptions.JSONDecodeError:
                        if attempt < 2:
                            continue
                    except Exception:
                        pass
                inserted_ok[i + j] = ok
                if not ok:
                    bt = BLOCK_TYPES.get(block.get("block_type"), "?")
                    print(f"      ❌ [{i+j}] {bt}")

    success_count = sum(inserted_ok)
    print(f"   Phase 1: {success_count}/{len(first_blocks)}")

    # === Phase 2: 填充 cell ===
    print("\n📥 Phase 2: 填充表格 cell 内容...")

    doc_children = client.get_children(doc_id, doc_id)
    doc_tables = []
    for idx, item in enumerate(doc_children):
        if item.get("block_type") in (19, 31):
            doc_tables.append((idx, item))

    cells_updated = 0
    cells_skipped = 0
    used_doc_indices = set()

    for ti, tinfo in enumerate(split_table_infos):
        ni = tinfo["new_index"]

        if not inserted_ok[ni]:
            print(f"   ⚠️ 表格#{ti+1} ({tinfo['rows']}×{tinfo['cols']}): 未创建")
            cells_skipped += len(tinfo["cell_ids"])
            continue

        # 找匹配的文档表格
        prev_count = sum(1 for k in range(ni) if inserted_ok[k])

        best = None
        best_dist = 999999
        for di, (orig_idx, dt) in enumerate(doc_tables):
            if di in used_doc_indices:
                continue
            dt_prop = dt.get("table", {}).get("property", {})
            if (dt_prop.get("row_size") == tinfo["rows"] and
                    dt_prop.get("column_size") == tinfo["cols"]):
                dist = abs(orig_idx - prev_count)
                if dist < best_dist:
                    best_dist = dist
                    best = (di, dt)

        if not best:
            print(f"   ⚠️ 表格#{ti+1} ({tinfo['rows']}×{tinfo['cols']}): 未匹配")
            cells_skipped += len(tinfo["cell_ids"])
            continue

        di, doc_table = best
        used_doc_indices.add(di)
        doc_table_id = doc_table["block_id"]
        doc_cell_ids = doc_table.get("table", {}).get("cells", [])

        if len(doc_cell_ids) != len(tinfo["cell_ids"]):
            print(f"   ⚠️ 表格#{ti+1}: cell 数不匹配")
            cells_skipped += len(tinfo["cell_ids"])
            continue

        cell_blocks = client.get_children(doc_id, doc_table_id)
        cell_map = {}
        for cb in cell_blocks:
            if cb.get("block_type") == 32:
                cell_map[cb["block_id"]] = cb

        ok_count = 0
        for ci in range(len(tinfo["cell_ids"])):
            convert_cell_id = tinfo["cell_ids"][ci]
            doc_cell_id = doc_cell_ids[ci]
            doc_cell = cell_map.get(doc_cell_id)
            if not doc_cell:
                cells_skipped += 1
                continue

            elements = get_cell_elements(all_blocks, convert_cell_id)
            if not elements:
                cells_skipped += 1
                continue

            doc_cell_children = doc_cell.get("children", [])
            if not doc_cell_children:
                cells_skipped += 1
                continue

            text_block_id = doc_cell_children[0]
            if client.update_text(doc_id, text_block_id, elements):
                ok_count += 1
            else:
                cells_skipped += 1

        print(f"   ✅ 表格#{ti+1} ({tinfo['rows']}×{tinfo['cols']}): {ok_count}/{len(tinfo['cell_ids'])} cells")
        cells_updated += ok_count

    # === 结果 ===
    fail_count = len(first_blocks) - success_count
    print(f"\n{'='*60}")
    print(f"📊 结果")
    print(f"{'='*60}")
    print(f"   结构: {success_count}/{len(first_blocks)} blocks")
    print(f"   Cell: {cells_updated} 成功, {cells_skipped} 跳过")
    print(f"   📎 {url}")
    print(f"{'='*60}")

    if cells_skipped == 0 and fail_count == 0:
        print("✅ 全部成功！")
        return 0
    else:
        print(f"⚠️ {fail_count} blocks + {cells_skipped} cells 未成功")
        return 1


if __name__ == "__main__":
    sys.exit(main())

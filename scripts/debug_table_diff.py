#!/usr/bin/env python3
"""对比 5×3（成功）和 11×4（失败）表格的完整结构差异"""
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

for i, b in enumerate(first_blocks):
    if b.get("block_type") == 31:
        prop = b.get("table", {}).get("property", {})
        rows = prop.get("row_size", 0)
        cols = prop.get("column_size", 0)
        label = "11×4" if rows == 11 else "6×2" if rows == 6 else "5×3"
        print(f"\n=== Block[{i}] {label} ({rows}×{cols}) ===")
        # 打印除 children 和 cells 外的所有字段
        clean = json.loads(json.dumps(b))
        clean.pop("children", None)
        clean.pop("block_id", None)
        clean.get("table", {}).pop("cells", None)
        print(json.dumps(clean, indent=2, ensure_ascii=False))

#!/usr/bin/env python3
"""查看失败的 block"""
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
blocks = result["blocks"]
first_ids = set(result["first_level_block_ids"])
first_blocks = [b for b in blocks if b["block_id"] in first_ids]

def clean(obj):
    if isinstance(obj, dict):
        obj.pop("merge_info", None)
        for v in obj.values(): clean(v)
    elif isinstance(obj, list):
        for item in obj: clean(item)
clean(first_blocks)

# Block index 89
print(f"Block[89]:")
print(json.dumps(first_blocks[89], indent=2, ensure_ascii=False))

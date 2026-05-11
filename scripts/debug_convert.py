#!/usr/bin/env python3
"""调试 convert API 返回结构"""
import requests, json, time

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

# 获取 token
resp = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal", json={
    "app_id": APP_ID, "app_secret": APP_SECRET,
})
token = resp.json()["tenant_access_token"]

# 读取 markdown
with open("/root/code/wyRss/output/AI-digest_20260327_035845.md") as f:
    md = f.read()

# 调用 convert API - 只用前 500 字符测试
short_md = md[:2000]
print(f"发送 {len(short_md)} 字符的 Markdown...")
resp = requests.post(f"{BASE_URL}/docx/v1/documents/blocks/convert", 
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
    json={"content_type": "markdown", "content": short_md})
data = resp.json()
print(f"code: {data.get('code')}")
print(f"msg: {data.get('msg')}")

# 打印 data 结构的 keys
d = data.get("data", {})
print(f"data keys: {list(d.keys())}")
print(f"data 字段:")
for k, v in d.items():
    if isinstance(v, list):
        print(f"  {k}: list[{len(v)}]")
        if v:
            print(f"    第一个元素的 keys: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
    elif isinstance(v, dict):
        print(f"  {k}: dict with keys {list(v.keys())[:10]}")
    else:
        print(f"  {k}: {str(v)[:200]}")

# 打印完整返回（截断）
print(f"\n完整返回（前 3000 字符）:")
print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])

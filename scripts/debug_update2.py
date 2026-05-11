#!/usr/bin/env python3
"""测试各种 update 格式"""
import requests, json

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试] update"}).json()["data"]["document"]["document_id"]

# 插入 text block
r = requests.post(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    headers=h, json={"children": [{
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": "original"}}], "style": {}}
    }], "index": -1})
block_id = r.json()["data"]["children"][0]["block_id"]

# 尝试不同的 update 格式
formats = [
    # 格式1: 带 document_id + block_id
    ("格式1: 带doc_id+block_id", {
        "document_id": doc_id,
        "block_id": block_id,
        "text": {"elements": [{"text_run": {"content": "test1"}}], "style": {}}
    }),
    # 格式2: 只带 text
    ("格式2: 只带 text", {
        "text": {"elements": [{"text_run": {"content": "test2"}}], "style": {}}
    }),
    # 格式3: 带 text_element_style
    ("格式3: 带 style", {
        "text": {
            "elements": [{"text_run": {"content": "test3", "text_element_style": {}}}],
            "style": {}
        }
    }),
    # 格式4: 使用 update_text_elements
    ("格式4: update_text_elements", {
        "update_text_elements": {
            "elements": [{"text_run": {"content": "test4"}}]
        }
    }),
    # 格式5: 最简格式
    ("格式5: 最简", {
        "text": {"elements": [{"text_run": {"content": "test5"}}]}
    }),
]

for name, body in formats:
    r = requests.patch(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{block_id}",
        headers=h, json=body)
    d = r.json()
    print(f"{name}: code={d.get('code')} msg={d.get('msg','')[:100]}")
    if d.get("code") == 0:
        # 验证
        r2 = requests.get(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{block_id}", headers=h)
        d2 = r2.json()
        content = ""
        for el in d2.get("data", {}).get("block", {}).get("text", {}).get("elements", []):
            content += el.get("text_run", {}).get("content", "")
        print(f"  ✅ 内容变为: '{content}'")

# 查看飞书 API 文档
print(f"\n\n--- 查看 API 错误详情 ---")
r = requests.patch(f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{block_id}",
    headers=h, json={
        "text": {"elements": [{"text_run": {"content": "test6"}}], "style": {}}
    })
d = r.json()
print(json.dumps(d, indent=2, ensure_ascii=False))

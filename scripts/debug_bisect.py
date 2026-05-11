#!/usr/bin/env python3
"""二分查找问题 block"""
import requests, json

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

token = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()["tenant_access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# 用之前的文档
doc_id = requests.post(f"{BASE_URL}/docx/v1/documents", headers=h,
    json={"title": "[调试4] 定位"}).json()["data"]["document"]["document_id"]

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

url = f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"

def test_batch(batch):
    resp = requests.post(url, headers=h, json={"children": batch, "index": -1})
    try:
        d = resp.json()
        return d.get("code") == 0
    except:
        return False

# 之前已知前25个有问题，二分查找
problematic = list(range(25))
while len(problematic) > 1:
    mid = len(problematic) // 2
    left = problematic[:mid]
    right = problematic[mid:]
    
    # 用一个成功 block + 测试 block 的方式
    left_batch = [first_blocks[i] for i in left]
    right_batch = [first_blocks[i] for i in right]
    
    left_ok = test_batch(left_batch)
    right_ok = test_batch(right_batch)
    
    if not left_ok and not right_ok:
        print(f"  两边都失败, 进一步二分左边: {left}")
        problematic = left
    elif not left_ok:
        print(f"  左边失败({len(left)}), 右边成功({len(right)})")
        problematic = left
    elif not right_ok:
        print(f"  左边成功({len(left)}), 右边失败({len(right)})")
        problematic = right
    else:
        print(f"  两边都成功! 可能是组合问题")
        break

print(f"\n问题 block 索引: {problematic}")
for idx in problematic[:3]:
    b = first_blocks[idx]
    print(f"\nBlock[{idx}]: type={b.get('block_type')}, id={b['block_id']}")
    print(json.dumps(b, ensure_ascii=False, indent=2)[:500])

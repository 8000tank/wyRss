#!/usr/bin/env python3
"""
通过飞书官方 Convert API 将 Markdown（含表格）写入飞书文档。

流程：
1. 获取 tenant_access_token
2. 创建飞书文档
3. 调用 convert API 将 Markdown 转为 blocks
4. 清理 merge_info（只读字段，不删会报错）
5. 批量插入 blocks 到文档
"""

import json
import sys
import re
import requests
from datetime import datetime

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"


def get_token():
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def create_doc(token, title):
    resp = requests.post(
        f"{BASE_URL}/docx/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title}
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"创建文档失败: {data}")
    doc_id = data["data"]["document"]["document_id"]
    return doc_id


def convert_markdown_to_blocks(token, markdown_content):
    """调用飞书官方 convert API，将 Markdown 转为 blocks"""
    resp = requests.post(
        f"{BASE_URL}/docx/v1/documents/blocks/convert",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        },
        json={
            "content_type": "markdown",
            "content": markdown_content
        }
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Convert 失败: {data.get('msg', '')} (code: {data.get('code')})")

    # API 返回 blocks 是列表，转成 dict 以 block_id 为 key
    blocks_list = data["data"]["blocks"]
    blocks = {b["block_id"]: b for b in blocks_list}
    first_level_block_ids = data["data"].get("first_level_block_ids", [])
    return blocks, first_level_block_ids


def clean_blocks_for_insert(blocks, first_level_block_ids):
    """清理 blocks：移除只读字段 merge_info（表格 block 有此字段，插入会报错）"""
    def clean_block(block_id):
        if block_id not in blocks:
            return
        block = blocks[block_id]
        # 清理 table 的 merge_info
        if "table" in block and "property" in block["table"]:
            if "merge_info" in block["table"]["property"]:
                del block["table"]["property"]["merge_info"]
        # 递归清理子 blocks
        if "children" in block:
            for child_id in block["children"]:
                clean_block(child_id)

    for block_id in first_level_block_ids:
        clean_block(block_id)


def insert_blocks(token, doc_id, blocks, first_level_block_ids):
    """使用 descendant API 批量插入嵌套 blocks，每次最多 50 个一级 block"""
    batch_size = 50
    total = len(first_level_block_ids)
    success = 0

    for i in range(0, total, batch_size):
        batch_ids = first_level_block_ids[i:i + batch_size]
        # 收集这一批所有需要的 block（一级 + 所有子孙）
        needed_ids = set(batch_ids)
        queue = list(batch_ids)
        while queue:
            bid = queue.pop()
            if bid in blocks:
                block = blocks[bid]
                if "children" in block:
                    for child_id in block["children"]:
                        if child_id not in needed_ids:
                            needed_ids.add(child_id)
                            queue.append(child_id)

        descendants = [blocks[bid] for bid in needed_ids if bid in blocks]

        resp = requests.post(
            f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/descendant",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "children_id": batch_ids,
                "descendants": descendants,
                "index": -1
            }
        )
        if resp.status_code == 200:
            resp_data = resp.json()
            if resp_data.get("code") == 0:
                success += len(batch_ids)
                print(f"  ✅ 批次 {i // batch_size + 1}: 插入 {len(batch_ids)} 个一级 block（共 {len(descendants)} 个 block）")
            else:
                print(f"  ⚠️ 批次 {i // batch_size + 1} API 错误: {resp_data.get('msg', '')} (code: {resp_data.get('code')})")
        else:
            print(f"  ⚠️ 批次 {i // batch_size + 1} HTTP 错误: {resp.status_code}")
            print(f"     body: {resp.text[:500]}")
            # 频率限制时等待重试
            if resp.status_code == 429:
                import time
                time.sleep(2)
                # 重试一次
                resp2 = requests.post(
                    f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/descendant",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=utf-8"
                    },
                    json={
                        "children_id": batch_ids,
                        "descendants": descendants,
                        "index": -1
                    }
                )
                if resp2.status_code == 200 and resp2.json().get("code") == 0:
                    success += len(batch_ids)
                    print(f"  ✅ 批次 {i // batch_size + 1}: 重试成功!")
                else:
                    print(f"  ❌ 批次 {i // batch_size + 1}: 重试仍然失败")

    return success, total


def main():
    if len(sys.argv) < 2:
        print("用法: python md_to_feishu_doc.py <markdown文件路径> [文档标题]")
        sys.exit(1)

    md_file = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else f"文档 {datetime.now().strftime('%Y-%m-%d')}"

    print("=" * 60)
    print("📄 Markdown → 飞书文档（官方 Convert API）")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 读取 Markdown
    print(f"\n[1/5] 读取 Markdown: {md_file}")
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"  ✅ 已读取 {len(content)} 字符")

    # 2. 获取 token
    print("[2/5] 获取 access token...")
    token = get_token()
    print("  ✅ Token 获取成功")

    # 3. 创建文档
    print(f"[3/5] 创建飞书文档: {title}")
    doc_id = create_doc(token, title)
    doc_url = f"https://feishu.cn/docx/{doc_id}"
    print(f"  ✅ 文档已创建: {doc_url}")

    # 4. 转换 Markdown → blocks
    print("[4/5] 调用 Convert API 转换 Markdown...")
    blocks, first_level_block_ids = convert_markdown_to_blocks(token, content)
    print(f"  ✅ 转换成功: {len(first_level_block_ids)} 个一级 block，共 {len(blocks)} 个 block（含子块）")

    # 5. 清理并插入
    print("[5/5] 插入 blocks 到文档...")
    clean_blocks_for_insert(blocks, first_level_block_ids)
    success, total = insert_blocks(token, doc_id, blocks, first_level_block_ids)
    print(f"  完成: {success}/{total} 个一级 block 插入成功")

    print()
    print("=" * 60)
    if success == total:
        print("✅✅✅ 全部成功!")
    else:
        print(f"⚠️ 部分失败: {success}/{total}")
    print(f"📄 文档链接: {doc_url}")
    print("=" * 60)

    return doc_url


if __name__ == "__main__":
    main()

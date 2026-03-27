#!/usr/bin/env python3
"""
MD → 飞书文档（支持标题、加粗、引用块）
简化版：引用块直接去掉 > 前缀显示
"""

import requests
import re

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"


def get_token():
    resp = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]


def create_doc(token, title):
    resp = requests.post(f"{BASE_URL}/docx/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title})
    doc_id = resp.json()["data"]["document"]["document_id"]
    return doc_id, f"https://feishu.cn/docx/{doc_id}"


def parse_md(content):
    """将 Markdown 解析为 Feishu blocks"""
    blocks = []
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # 空行跳过
        if not line.strip():
            i += 1
            continue

        # ===== 引用块：去掉 > 前缀 =====
        if line.startswith('>'):
            # 收集多行引用
            parts = []
            while i < len(lines) and lines[i].startswith('>'):
                q = lines[i].lstrip('>').strip()
                if q:
                    parts.append(q)
                i += 1
            # 合并为一段，斜体显示引用标记
            text = ' '.join(parts)
            blocks.append(text_block(f"「引用」{text}"))
            continue

        # ===== 标题 =====
        hm = re.match(r'^(#{1,3})\s+(.*)', line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2)
            blocks.append(heading_block(level, text))
            i += 1
            continue

        # ===== 表格行（简化处理） =====
        if line.startswith('|'):
            # 去掉首尾 | 并显示内容
            cells = [c.strip() for c in line.strip('|').split('|')]
            # 分隔线行跳过
            if all(re.match(r'^-+$', c) for c in cells):
                i += 1
                continue
            text = ' '.join(cells)
            blocks.append(text_block(text))
            i += 1
            continue

        # ===== 普通文本 =====
        blocks.append(text_block(line))
        i += 1

    return blocks


def text_block(text):
    """普通文本块"""
    return {
        "block_type": 2,
        "text": {
            "elements": parse_inlines(text),
            "style": {"align": 1, "folded": False}
        }
    }


def heading_block(level, text):
    """标题块 h1/h2/h3"""
    bt = {1: 3, 2: 4, 3: 5}[level]
    return {
        "block_type": bt,
        f"heading{level}": {
            "elements": parse_inlines(text),
            "style": {"align": 1, "folded": False}
        }
    }


def parse_inlines(text):
    """解析行内样式：**bold**"""
    elements = []
    pattern = re.compile(r'\*\*(.+?)\*\*')
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            elements.append({"type": "text_run", "text_run": {"content": text[last:m.start()]}})
        elements.append({"type": "text_run", "text_run": {"content": m.group(1), "text_element_style": {"bold": True}}})
        last = m.end()
    if last < len(text):
        elements.append({"type": "text_run", "text_run": {"content": text[last:]}})
    if not elements:
        elements.append({"type": "text_run", "text_run": {"content": text}})
    return elements


def write_blocks(token, doc_id, blocks):
    batch_size = 50
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i+batch_size]
        resp = requests.post(
            f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers={"Authorization": f"Bearer {token}"},
            json={"children": batch, "index": i}
        )
        if resp.status_code != 200 or resp.json().get("code") != 0:
            print(f"⚠️ 批次失败: {resp.json().get('msg', '')}")


def main():
    md_file = "/root/code/wyRss/output/AI-digest_20260323_134511.md"
    with open(md_file) as f:
        content = f.read()

    print("解析 Markdown...")
    blocks = parse_md(content)
    print(f"共 {len(blocks)} 个 blocks")

    token = get_token()
    doc_id, url = create_doc(token, "AI 日报 2026-03-23 (引用块修复版)")
    print(f"文档: {url}")

    write_blocks(token, doc_id, blocks)
    print("完成!")
    print(f"\n📄 {url}")


if __name__ == "__main__":
    main()

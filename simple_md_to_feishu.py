#!/usr/bin/env python3
"""
Simplified script to create Feishu document from markdown and return URL
"""
import requests
import json
import time
import re
import sys

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

def get_token():
    r = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET})
    d = r.json()
    if d["code"] != 0:
        raise Exception(f"token error: {d}")
    return d["tenant_access_token"]

def main():
    import sys
    md_file = sys.argv[1] if len(sys.argv) > 1 else "/root/code/wyRss/output/AI-digest_20260331_023522.md"
    
    # Read markdown file
    with open(md_file, "r", encoding="utf-8") as f:
        md = f.read()
    
    # Extract title from markdown
    m = re.match(r"^#\s+(.+)", md, re.MULTILINE)
    doc_title = m.group(1).strip() if m else "Untitled"
    
    print(f"📄 Markdown: {len(md)} 字符")
    print(f"📝 标题: {doc_title}")
    
    # Get token
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    
    # Create document
    r = requests.post(f"{BASE_URL}/docx/v1/documents", headers=headers, json={"title": doc_title})
    d = r.json()
    print(f"创建文档响应: {d}")
    
    if d["code"] != 0:
        print(f"❌ 创建文档失败: {d}")
        return 1
    
    doc_id = d["data"]["document"]["document_id"]
    url = f"https://feishu.cn/docx/{doc_id}"
    print(f"✅ 文档创建成功: {url}")
    
    # Simple markdown conversion (simplified version)
    print("🔄 正在转换Markdown...")
    
    # Simple block creation (text blocks only for speed)
    blocks = []
    
    # Create blocks for lines
    lines = md.split('\n')
    for line in lines:
        if line.startswith('# '):
            # H1
            blocks.append({
                "block_type": 3,
                "heading": {
                    "level": 1,
                    "elements": [{"text": {"content": line[2:]}, "type": "text"}]
                }
            })
        elif line.startswith('## '):
            # H2
            blocks.append({
                "block_type": 4,
                "heading": {
                    "level": 2,
                    "elements": [{"text": {"content": line[3:]}, "type": "text"}]
                }
            })
        elif line.startswith('### '):
            # H3
            blocks.append({
                "block_type": 5,
                "heading": {
                    "level": 3,
                    "elements": [{"text": {"content": line[4:]}, "type": "text"}]
                }
            })
        elif line.startswith('|') and '|' in line and line.count('|') >= 3:
            # Table (simplified - just skip for now)
            continue
        elif line.startswith('- '):
            # Bullet list
            blocks.append({
                "block_type": 12,
                "paragraph": {
                    "elements": [{"text": {"content": line[2:]}, "type": "text"}]
                }
            })
        elif line.strip():
            # Regular paragraph
            blocks.append({
                "block_type": 2,
                "paragraph": {
                    "elements": [{"text": {"content": line}, "type": "text"}]
                }
            })
    
    print(f"📦 创建了 {len(blocks)} 个文本块")
    
    # Insert blocks
    for i in range(0, len(blocks), 10):  # Insert in batches of 10
        batch = blocks[i:i+10]
        time.sleep(0.1)
        try:
            r = requests.post(
                f"{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                headers=headers, 
                json={"children": batch, "index": -1}
            )
            d = r.json()
            if d["code"] != 0:
                print(f"⚠️ 批次 {i//10+1} 失败: {d}")
            else:
                print(f"✅ 批次 {i//10+1}: {len(batch)} blocks")
        except Exception as e:
            print(f"⚠️ 批次 {i//10+1} 异常: {e}")
    
    print(f"\n📎 完整文档: {url}")
    print(f"✅ 转换完成!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
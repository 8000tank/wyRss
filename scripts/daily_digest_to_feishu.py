#!/usr/bin/env python3
"""
wyRss 日报生成脚本
仅运行 wyRss 生成日报 Markdown 文件，打印文件路径供后续处理。
"""

import os
import glob
import subprocess
from datetime import datetime

WYRSS_DIR = "/root/code/wyRss"
OUTPUT_DIR = "/root/code/wyRss/output"


def run_wyrss():
    """运行 wyRss 生成日报"""
    print("[1/2] 运行 wyRss 生成日报...")
    result = subprocess.run(
        ["uv", "run", "python", "-m", "src.main"],
        cwd=WYRSS_DIR,
        capture_output=True,
        text=True,
        timeout=600
    )
    if result.returncode != 0:
        raise Exception(f"wyRss 运行失败: {result.stderr}")
    print("✅ wyRss 运行成功!")
    md_files = glob.glob(os.path.join(OUTPUT_DIR, "AI-digest_*.md"))
    if not md_files:
        raise Exception("未找到生成的日报文件")
    latest_md = max(md_files, key=os.path.getmtime)
    print(f"📄 最新日报: {latest_md}")
    return latest_md


def main():
    print("=" * 60)
    print("🤖 每日日报生成")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    try:
        md_file = run_wyrss()
        print()
        print("=" * 60)
        print("✅ 日报生成成功!")
        print(f"📄 文件路径: {md_file}")
        print("=" * 60)
        return md_file
    except Exception as e:
        print(f"\n❌ 日报生成失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

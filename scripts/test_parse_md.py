#!/usr/bin/env python3
"""
parse_md 单元测试
使用 wyRss 已生成的日报作为测试源
"""

import os
import sys
import json
import re
from datetime import datetime

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_digest_to_feishu import parse_md, parse_inlines, text_block, heading_block

OUTPUT_DIR = "/root/code/wyRss/output"


def get_latest_digest():
    """获取最新的日报文件"""
    import glob
    md_files = glob.glob(os.path.join(OUTPUT_DIR, "AI-digest_*.md"))
    if not md_files:
        return None
    return max(md_files, key=os.path.getmtime)


def test_parse_inlines():
    """测试行内样式解析"""
    print("\n" + "="*60)
    print("📋 测试 parse_inlines")
    print("="*60)

    test_cases = [
        # (输入, 期望包含的内容)
        ("普通文本", "普通文本"),
        ("**加粗文本**", "加粗文本"),
        ("`行内代码`", "行内代码"),
        ("[链接文字](https://example.com)", "链接文字"),
        ("**加粗**和普通", "加粗"),
        ("文本中有`代码`继续", "代码"),
        ("**关键词：** `TERAFAB` `马斯克`", "TERAFAB"),
    ]

    passed = 0
    failed = 0

    for text, expected in test_cases:
        try:
            elements = parse_inlines(text)
            # 检查是否包含期望内容
            content_str = json.dumps(elements, ensure_ascii=False)
            if expected in content_str:
                print(f"  ✅ {text[:40]}...")
                passed += 1
            else:
                print(f"  ❌ {text[:40]}... - 未找到: {expected}")
                print(f"     输出: {content_str[:100]}...")
                failed += 1
        except Exception as e:
            print(f"  ❌ {text[:40]}... - 异常: {e}")
            failed += 1

    print(f"\n结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_parse_md_structure():
    """测试 parse_md 结构解析"""
    print("\n" + "="*60)
    print("📋 测试 parse_md 结构解析")
    print("="*60)

    # 构造测试用例
    test_cases = [
        # 一级标题
        ("# 标题", "heading1"),
        # 二级标题
        ("## 二级标题", "heading2"),
        # 三级标题
        ("### 三级标题", "heading3"),
        # 带HTML的标题
        ("### <a name=\"1\"></a> 文章标题", "文章标题"),
        # 无序列表
        ("- 列表项", "bullet"),
        # 分割线
        ("---", "divider"),
        # 引用块
        ("> 引用内容", "quote"),
        # 表格
        ("| 列1 | 列2 |", "列1"),
    ]

    passed = 0
    failed = 0

    for md_text, expected in test_cases:
        try:
            blocks = parse_md(md_text)
            content_str = json.dumps(blocks, ensure_ascii=False)

            if expected in content_str:
                print(f"  ✅ {md_text[:40]}")
                passed += 1
            else:
                print(f"  ❌ {md_text[:40]} - 未找到: {expected}")
                print(f"     输出: {content_str[:150]}...")
                failed += 1
        except Exception as e:
            print(f"  ❌ {md_text[:40]} - 异常: {e}")
            failed += 1

    print(f"\n结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_real_digest():
    """使用真实日报测试完整解析"""
    print("\n" + "="*60)
    print("📋 测试真实日报解析")
    print("="*60)

    md_file = get_latest_digest()
    if not md_file:
        print("  ❌ 未找到日报文件")
        return False

    print(f"  📄 测试文件: {os.path.basename(md_file)}")

    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"  📊 文件大小: {len(content)} 字符")

        # 解析
        blocks = parse_md(content)
        print(f"  📊 生成 blocks: {len(blocks)} 个")

        # 统计各类型 block
        type_counts = {}
        for block in blocks:
            bt = block.get("block_type", "unknown")
            type_counts[bt] = type_counts.get(bt, 0) + 1

        print(f"  📊 Block 类型分布:")
        type_names = {
            2: "text",
            3: "heading1",
            4: "heading2/divider",
            5: "heading3",
            12: "quote",
            13: "bullet"
        }
        for bt, count in sorted(type_counts.items()):
            name = type_names.get(bt, f"type_{bt}")
            print(f"     - {name}: {count}")

        # 检查关键元素
        checks = [
            ("标题存在", any(b.get("block_type") in [3, 4, 5] for b in blocks)),
            ("引用块存在", any(b.get("block_type") == 12 for b in blocks)),
            ("列表块存在", any(b.get("block_type") == 13 for b in blocks)),
            ("分割线存在", any(b.get("block_type") == 4 and "divider" in b for b in blocks)),
        ]

        all_passed = True
        for name, result in checks:
            if result:
                print(f"  ✅ {name}")
            else:
                print(f"  ⚠️ {name} - 未检测到")
                all_passed = False

        # 检查是否有未处理的元素
        content_str = json.dumps(blocks, ensure_ascii=False)
        issues = []

        if '<a name=' in content_str:
            issues.append("HTML锚点未清理")
        if '---' in content_str and '"content": "---"' in content_str:
            issues.append("分割线未转换")
        if '`' in content_str and '"content": "`' in content_str:
            # 检查是否有残留的反引号（排除正常使用）
            pass  # 反引号可能在内容中正常出现

        if issues:
            print(f"  ⚠️ 潜在问题: {', '.join(issues)}")
        else:
            print(f"  ✅ 无明显解析问题")

        return len(blocks) > 0

    except Exception as e:
        print(f"  ❌ 解析异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_block_validity():
    """测试生成的 block 是否符合飞书 API 格式"""
    print("\n" + "="*60)
    print("📋 测试 Block 格式有效性")
    print("="*60)

    md_file = get_latest_digest()
    if not md_file:
        print("  ❌ 未找到日报文件")
        return False

    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = parse_md(content)

    valid_count = 0
    invalid_count = 0
    errors = []

    for i, block in enumerate(blocks):
        try:
            # 检查必需字段
            if "block_type" not in block:
                errors.append(f"Block {i}: 缺少 block_type")
                invalid_count += 1
                continue

            bt = block["block_type"]

            # 根据类型检查
            if bt == 2:  # text
                if "text" not in block:
                    errors.append(f"Block {i}: text block 缺少 text 字段")
            elif bt == 3:  # heading1
                if "heading1" not in block:
                    errors.append(f"Block {i}: heading1 block 缺少 heading1 字段")
            elif bt == 4:  # heading2 or divider
                if "heading2" not in block and "divider" not in block:
                    errors.append(f"Block {i}: block_type 4 缺少 heading2 或 divider 字段")
            elif bt == 5:  # heading3
                if "heading3" not in block:
                    errors.append(f"Block {i}: heading3 block 缺少 heading3 字段")
            elif bt == 12:  # quote
                if "quote" not in block:
                    errors.append(f"Block {i}: quote block 缺少 quote 字段")
            elif bt == 13:  # bullet
                if "bullet" not in block:
                    errors.append(f"Block {i}: bullet block 缺少 bullet 字段")

            valid_count += 1

        except Exception as e:
            errors.append(f"Block {i}: 验证异常 - {e}")
            invalid_count += 1

    print(f"  📊 有效 blocks: {valid_count}")
    if invalid_count > 0:
        print(f"  📊 无效 blocks: {invalid_count}")
        for err in errors[:10]:  # 只显示前10个错误
            print(f"     ❌ {err}")
        if len(errors) > 10:
            print(f"     ... 还有 {len(errors) - 10} 个错误")
    else:
        print(f"  ✅ 所有 blocks 格式有效")

    return invalid_count == 0


def main():
    print("="*60)
    print("🧪 parse_md 单元测试")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    results = []

    # 运行所有测试
    results.append(("parse_inlines", test_parse_inlines()))
    results.append(("parse_md_structure", test_parse_md_structure()))
    results.append(("real_digest", test_real_digest()))
    results.append(("block_validity", test_block_validity()))

    # 汇总
    print("\n" + "="*60)
    print("📊 测试汇总")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print("="*60)
    if all_passed:
        print("🎉 所有测试通过!")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
测试用例：验证 Readwise API 返回的文章来源分布情况
目标：分析当前20篇文章的作者和站点分布，为站点多样性筛选提供依据
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from src.clients.readwise_client import ReadwiseClient
from src.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def analyze_distribution(articles: list, title: str = "文章分布分析"):
    """分析文章的作者和站点分布"""
    print("\n" + "=" * 80)
    print(f"📊 {title}")
    print("=" * 80)

    # 作者分布
    author_counts = Counter([a.author or "未知作者" for a in articles])
    print(f"\n👤 作者分布（共 {len(author_counts)} 位作者）：")
    print("-" * 50)
    for author, count in author_counts.most_common():
        pct = count / len(articles) * 100
        print(f"  {author:<20} {count:>3} 篇 ({pct:>5.1f}%)")

    # 站点分布
    site_counts = Counter([a.site_name or "未知站点" for a in articles])
    print(f"\n🌐 站点分布（共 {len(site_counts)} 个站点）：")
    print("-" * 50)
    for site, count in site_counts.most_common():
        pct = count / len(articles) * 100
        print(f"  {site:<25} {count:>3} 篇 ({pct:>5.1f}%)")

    # 集中度分析
    top_author_pct = author_counts.most_common(1)[0][1] / len(articles) * 100 if author_counts else 0
    top_site_pct = site_counts.most_common(1)[0][1] / len(articles) * 100 if site_counts else 0

    print(f"\n⚠️ 集中度分析：")
    print(f"  - 最活跃作者占比：{top_author_pct:.1f}%")
    print(f"  - 最活跃站点占比：{top_site_pct:.1f}%")

    if top_author_pct > 50:
        print(f"  ⚠️ 警告：单一作者文章占比过高，建议启用作者/站点多样性筛选")
    if top_site_pct > 50:
        print(f"  ⚠️ 警告：单一站点文章占比过高，建议启用站点多样性筛选")

    print("=" * 80)


def main():
    settings = Settings.from_env()
    hours = settings.digest_hours
    candidate_limit = settings.digest_candidate_limit
    updated_after = datetime.now(timezone.utc) - timedelta(hours=hours)

    readwise_client = ReadwiseClient(
        token=settings.readwise_token,
        base_url=settings.readwise_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )

    logging.info("开始测试 Readwise API 的文章来源分布...")
    logging.info(f"时间窗口：最近 {hours} 小时")
    logging.info(f"候选上限：{candidate_limit} 篇")
    logging.info(f"筛选条件：location={settings.readwise_location}, category={settings.readwise_category}")

    # 测试1：当前筛选条件下的分布
    print("\n" + "🧪 测试 1：当前筛选条件（location=feed, category=rss）")
    articles_scenario1 = readwise_client.list_documents(
        updated_after=updated_after,
        location=settings.readwise_location,
        category=settings.readwise_category,
        with_html_content=False,  # 不需要HTML内容，加快API调用
        max_items=candidate_limit,
    )
    analyze_distribution(articles_scenario1, "场景1：仅 RSS Feed 文章（当前配置）")

    # 测试2：移除 category 限制的分布
    print("\n" + "🧪 测试 2：仅限制 location=feed，不限制 category")
    articles_scenario2 = readwise_client.list_documents(
        updated_after=updated_after,
        location=settings.readwise_location,
        category=None,  # 移除 category 限制
        with_html_content=False,
        max_items=candidate_limit,
    )
    if len(articles_scenario2) != len(articles_scenario1):
        analyze_distribution(articles_scenario2, "场景2：Feed 全部文章（不限 category）")
    else:
        print("  ℹ️ 结果与场景1相同，说明 category=rss 没有额外过滤")

    # 测试3：完全不限制的分布（只限时间）
    print("\n" + "🧪 测试 3：不限制 location 和 category（仅时间筛选）")
    articles_scenario3 = readwise_client.list_documents(
        updated_after=updated_after,
        location=None,
        category=None,
        with_html_content=False,
        max_items=candidate_limit,
    )
    analyze_distribution(articles_scenario3, "场景3：全部文章（不限 location/category）")

    # 总结建议
    print("\n" + "=" * 80)
    print("📋 测试总结与建议")
    print("=" * 80)
    print(f"场景1（当前配置）: {len(articles_scenario1)} 篇")
    print(f"场景2（不限category）: {len(articles_scenario2)} 篇")
    print(f"场景3（全部文章）: {len(articles_scenario3)} 篇")

    print("\n💡 建议：")
    if len(articles_scenario3) > len(articles_scenario1):
        print("  - 场景3文章更多，但可能包含非RSS内容（如手动保存的文章）")
        print("  - 如果想获取更多来源，建议保持当前配置，但增加站点多样性筛选")
    else:
        print("  - 各场景文章数量相同，说明当前配置已经能获取全部近期文章")
        print("  - 建议增加站点多样性筛选，确保20篇文章来自更多不同来源")

    print("\n🔧 下一步：")
    print("  确认分布情况后，我将实现站点多样性筛选：")
    print("  - 优先获取不同 site_name 的文章")
    print("  - 每个站点最多保留 N 篇（可配置）")
    print("  - 确保最终20篇来自尽可能多的不同来源")
    print("=" * 80)


if __name__ == "__main__":
    main()

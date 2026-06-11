"""Source/site classification used by both topic diversity and content-type prompts.

Also exposes :func:`publisher_key` — the canonical "who really published this"
key used by diversity caps. Necessary because aggregator platforms (most
notably WeChat) put the publication name in ``author`` while leaving
``site_name`` set to a single shared platform label.


Two related decisions live here so they share one source of truth:

- ``topic_for(article, allowed_topics)`` -> coarse subject bucket
  (``ai`` / ``security`` / ``infra`` / ``research`` / ``business`` / ``other``).
  Used by ``select_diverse_candidates`` to spread candidates across topics.

- ``content_type_for(article)`` -> rough content shape
  (``newsletter`` / ``rss-news`` / ``research`` / ``security-advisory`` / ``general``).
  Used by ``score_articles`` to feed the LLM a self-aware label so long-form
  newsletters / papers don't get penalised on actionability.

The mapping table is intentionally simple to maintain: just extend the
``_SITE_RULES`` list with another (matcher, topic, content_type) tuple.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from src.models import Article


@dataclass(slots=True, frozen=True)
class _Rule:
    needles: tuple[str, ...]  # case-insensitive substrings to match against site/source/author/url
    topic: str
    content_type: str


# Order matters only for documentation; matching is by substring on any field.
_SITE_RULES: list[_Rule] = [
    # --- AI media (Chinese) ---
    _Rule(("量子位", "qbitai"), "ai", "rss-news"),
    _Rule(("新智元",), "ai", "rss-news"),
    _Rule(("机器之心", "jiqizhixin"), "ai", "rss-news"),
    _Rule(("傅盛",), "ai", "rss-news"),
    # --- AI companies / products (Chinese) ---
    _Rule(("deepseek",), "ai", "rss-news"),
    _Rule(("智谱",), "ai", "rss-news"),
    _Rule(("通义实验室", "通义", "tongyi"), "ai", "rss-news"),
    _Rule(("百度文心", "wenxin"), "ai", "rss-news"),
    _Rule(("腾讯混元", "混元", "hunyuan"), "ai", "rss-news"),
    _Rule(("阶跃星辰", "stepfun"), "ai", "rss-news"),
    _Rule(("字节跳动seed",), "ai", "rss-news"),
    _Rule(("minimax", "稀宇"), "ai", "rss-news"),
    _Rule(("月之暗面", "kimi", "moonshot"), "ai", "rss-news"),
    _Rule(("dify",), "ai", "rss-news"),
    _Rule(("jina ai", "jina"), "ai", "rss-news"),
    _Rule(("datawhale",), "ai", "rss-news"),
    _Rule(("山行ai", "shanxing"), "ai", "rss-news"),
    _Rule(("modelscope", "魔搭"), "ai", "rss-news"),
    # --- AI media (Chinese extended) ---
    _Rule(("ai前线", "leiphone"), "ai", "rss-news"),
    _Rule(("智东西", "zhidx"), "ai", "rss-news"),
    _Rule(("ai科技评论",), "ai", "rss-news"),
    _Rule(("通往agi之路", "waytoagi"), "ai", "rss-news"),
    _Rule(("智能涌现", "aixiv"), "ai", "rss-news"),
    _Rule(("青稞ai"), "ai", "rss-news"),
    _Rule(("paperagent",), "ai", "rss-news"),
    _Rule(("ainlp",), "ai", "rss-news"),
    _Rule(("deeptech", "deep tech"), "research", "research"),
    _Rule(("paperweekly",), "research", "research"),
    # --- AI media (English) ---
    _Rule(("the verge",), "ai", "rss-news"),
    _Rule(("mit technology review", "technologyreview"), "research", "research"),
    _Rule(("berkeley artificial intelligence", "bair"), "research", "research"),
    # --- Security ---
    _Rule(("玄武实验室", "腾讯玄武"), "security", "security-advisory"),
    _Rule(("奇安信", "qianxin"), "security", "security-advisory"),
    _Rule(("安全内参", "secrss"), "security", "security-advisory"),
    # --- Infra / cloud ---
    _Rule(("阿里云开发者", "aliyun"), "infra", "rss-news"),
    _Rule(("字节跳动技术团队",), "infra", "rss-news"),
    _Rule(("阿里技术",), "infra", "rss-news"),
    _Rule(("腾讯技术工程",), "infra", "rss-news"),
    _Rule(("腾讯云开发者",), "infra", "rss-news"),
    _Rule(("小米技术",), "infra", "rss-news"),
    _Rule(("快手技术",), "infra", "rss-news"),
    _Rule(("哔哩哔哩技术", "bilibili技术"), "infra", "rss-news"),
    _Rule(("蚂蚁技术", "anttech"), "infra", "rss-news"),
    _Rule(("钉钉", "dingtalk"), "infra", "rss-news"),
    _Rule(("飞书", "feishu", "lark"), "infra", "rss-news"),
    _Rule(("infoq",), "infra", "rss-news"),
    _Rule(("hellogithub",), "infra", "rss-news"),
    _Rule(("githubdaily",), "infra", "rss-news"),
    _Rule(("稀土掘金", "juejin"), "infra", "rss-news"),
    _Rule(("少数派", "sspai"), "other", "rss-news"),
    # --- Newsletters (Substack / hand-curated email) ---
    _Rule(("import ai", "jack clark"), "business", "newsletter"),
    _Rule(("ben's bites", "bens bites"), "business", "newsletter"),
    _Rule(("the neuron",), "business", "newsletter"),
    _Rule(("the code",), "business", "newsletter"),
    _Rule(("superhuman", "zain kahn"), "business", "newsletter"),
    _Rule(("substack",), "business", "newsletter"),
    # --- Reader product itself (we don't really want to highlight changelog) ---
    _Rule(("readwise & reader changelog", "readwise changelog"), "other", "general"),
]

# Fallback keyword -> topic when no _SITE_RULES match.
_TITLE_TOPIC_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("漏洞", "cve", "0day", "0-day", "exploit", "ransomware", "勒索", "apt", "钓鱼"), "security"),
    (("kubernetes", "k8s", "容器", "container", "云原生", "云计算", "serverless"), "infra"),
    (("paper", "arxiv", "论文", "neurips", "icml", "iclr", "cvpr", "acl"), "research"),
    (("llm", "gpt", " ai ", "agent", "大模型", "rag", "embedding", "transformer"), "ai"),
]


def _haystack(article: Article) -> str:
    parts = [
        article.site_name or "",
        article.source or "",
        article.author or "",
        article.canonical_url or "",
    ]
    return " ".join(parts).lower()


def _match_rule(article: Article) -> _Rule | None:
    haystack = _haystack(article)
    for rule in _SITE_RULES:
        for needle in rule.needles:
            if needle.lower() in haystack:
                return rule
    return None


def topic_for(article: Article, allowed_topics: list[str] | None = None) -> str:
    """Best-effort topic bucket for an article.

    If ``allowed_topics`` is provided, any inferred topic outside the whitelist
    gets normalised to ``other``. ``other`` is always implicitly allowed.
    """
    rule = _match_rule(article)
    topic = rule.topic if rule else None

    if topic is None and (article.category or "").strip().lower() == "email":
        topic = "business"

    if topic is None:
        title_haystack = " ".join(
            [
                article.title or "",
                " ".join(article.tags or []),
            ]
        ).lower()
        for keywords, candidate in _TITLE_TOPIC_KEYWORDS:
            if any(keyword in title_haystack for keyword in keywords):
                topic = candidate
                break

    if topic is None:
        topic = "other"

    if allowed_topics:
        normalized = [item.lower() for item in allowed_topics]
        if topic not in normalized:
            return "other"
    return topic


def content_type_for(article: Article) -> str:
    """Rough content-shape label fed into the LLM scoring prompt."""
    rule = _match_rule(article)
    if rule is not None:
        return rule.content_type

    category = (article.category or "").strip().lower()
    if category == "email":
        return "newsletter"

    host = urlparse(article.canonical_url or "").netloc.lower()
    if "arxiv" in host or "arxiv.org" in host:
        return "research"
    if "substack.com" in host:
        return "newsletter"

    return "general"


# Site names that are *aggregator platforms*, not real publications.
# When site_name matches one of these, the actual publication identity is in
# the article's author field, so diversity logic should key on author instead.
_AGGREGATOR_SITE_PATTERNS: tuple[str, ...] = (
    "weixin official accounts platform",
    "weixin official accounts",
    "微信公众号",
    "公众号平台",
    "substack.com",
    "substack",
    "medium.com",
)


def publisher_key(article: Article) -> str:
    """Best-effort 'which publication published this' key.

    Order:
    1. If ``site_name`` is set and is *not* a known aggregator label, use it.
    2. Otherwise prefer ``author`` (this is what fixes WeChat / Substack).
    3. Fall back to ``source`` -> URL hostname -> ``"unknown-source"``.
    """
    site_name = (article.site_name or "").strip()
    site_lower = site_name.lower()
    is_aggregator = any(pattern in site_lower for pattern in _AGGREGATOR_SITE_PATTERNS)

    if site_name and not is_aggregator:
        return site_lower

    author = (article.author or "").strip()
    if author:
        return author.lower()

    source = (article.source or "").strip()
    if source:
        return source.lower()

    host = urlparse(article.canonical_url or "").netloc.strip().lower()
    return host or "unknown-source"

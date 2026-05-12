# Readwise 日报生成器

从 Readwise Reader 拉取文章，经多维度筛选与 LLM 评分后输出 Markdown 日报。

## 技术栈

- Python 3.12+，使用 **uv** 管理依赖（`.python-version` 声明版本）
- `python-dotenv` 加载 `.env`；不存在时从 shell 环境变量读取
- OpenAI 兼容接口（智谱 GLM、MiniMax M2 等）

## 项目结构

```
src/
  main.py                  # CLI 入口与流水线编排
  config.py                # Settings + FetchBucket 数据类，环境变量解析
  models.py                # Article / ScoredArticle 数据模型
  clients/
    readwise_client.py     # Readwise Reader API 封装
    llm_client.py          # OpenAI 兼容 LLM 客户端
  pipeline/
    source_taxonomy.py     # 来源分类：topic / content_type / publisher_key
    filtering.py           # 过滤 + 预评分多样性选择
    ranking.py             # LLM 评分 + 终选多样性约束
  renderers/
    markdown_renderer.py   # Markdown 渲染与写入
scripts/
  dry_run_diagnostic.py    # 端到端诊断（真实 API + 假 LLM，exit 0/1）
tests/
  conftest.py              # 共享 fixture（mock_env_vars 等）
  unit/                    # 单元测试
  integration/             # 集成测试（API 连通、平衡流水线）
```

## 核心流水线

1. **拉取** — `ReadwiseClient.list_documents_by_buckets` 按多桶配置（category@location:max）拉取并按 document id 去重；无桶配置时回退到单桶路径
2. **过滤** — `filter_articles`：时间窗口 + 发布日期新鲜度 + 邮件噪音 + URL 去重
3. **预评分多样性** — `select_diverse_candidates`：按 (topic, source, author) 贪心均衡缩减 LLM 调用量
4. **LLM 评分** — `score_articles`：并发调用 LLM，prompt 包含内容类型标签（newsletter / research / rss-news 等）；校验必需字段，缺失时回退到 50 分
5. **终选多样性** — `_apply_diversity`：site + author 双维度硬约束（`DIGEST_MAX_PER_SITE` / `DIGEST_MAX_PER_AUTHOR`）
6. **渲染** — 输出 Markdown 到 `output/` 目录

## ⚠️ .env 格式约束

`.env` 文件通过 `source .env` 加载（cron 脚本），因此：

- **所有变量必须带 `export` 前缀**，否则变量不会传递给子进程（如 `send_feishu_msg.py`）
- **所有值必须用双引号包裹**，尤其是包含分号（`;`）、空格等 shell 特殊字符的值（如 `DIGEST_SCORING_FOCUS`）

Python 端通过 `python-dotenv` 直接读取 `.env`，不依赖 `export` 和引号，但为保持一致性，统一要求 export + 引号。

## 关键配置（环境变量 / .env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `READWISE_FETCH_BUCKETS` | 多桶规格：`category[@location]:max,...` | 空（回退单桶） |
| `DIGEST_MAX_PER_SITE` | 同一站点终选上限 | 2 |
| `DIGEST_MAX_PER_AUTHOR` | 同一作者终选上限 | 2 |
| `DIGEST_TOPIC_BUCKETS` | 题材白名单，逗号分隔 | ai,security,infra,research,business,other |
| `DIGEST_MAX_PUBLISHED_AGE_DAYS` | 排除超过 N 天的有日期文章 | 7 |
| `DIGEST_TIMEZONE` | 输出时间的时区 | Asia/Shanghai |
| `LLM_MAX_TOKENS` | LLM 最大输出 token | 4096 |
| `LLM_REASONING_SPLIT` | MiniMax M2 系列推理分割开关 | 自动检测 |

## 开发命令

```bash
uv run python -m src.main               # 运行日报生成
uv run python scripts/dry_run_diagnostic.py  # 端到端诊断
uv run pytest                            # 全部测试
uv run pytest tests/unit/                # 仅单元测试
uv run pytest tests/integration/         # 仅集成测试
```

## 诊断脚本说明

`scripts/dry_run_diagnostic.py` 调用真实 Readwise API，用确定性假 LLM（所有分数固定 80）跑完全流水线，输出三阶段分布表并运行 6 项自检。Exit 0 = 全部通过，Exit 1 = 有失败项（多数反映上游条件而非代码问题）。

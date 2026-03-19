# Readwise 日报生成器

一个最小可用的纯 Python 工作流：从 `Readwise Reader` 拉取文章，用 `OpenAI` 兼容接口做摘要与评分，然后输出本地 `Markdown` 日报。

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) - 2026年推荐的 Python 包管理器
- 一个 `Readwise Reader` API Token
- 一个 `OpenAI` 兼容模型配置（智谱、MiniMax 等）

## 安装

```bash
# 克隆或进入项目目录
cd readwise-digest

# uv 会自动创建虚拟环境并安装依赖
uv sync

# 复制环境变量模板
cp .env.example .env
# 然后编辑 .env 填入你的 API 密钥
```

## 快速开始

```bash
# 运行日报生成（自动使用 .venv）
uv run python -m src.main

# 或者使用项目命令
uv run readwise-digest
```

## 开发工作流

```bash
# 运行单元测试
uv run pytest tests/unit -v

# 运行集成测试（需要有效的 API Key）
uv run pytest tests/integration -v -m integration

# 添加新依赖
uv add package-name

# 添加开发依赖
uv add --dev package-name

# 更新锁定文件
uv lock

# 同步环境（严格使用 uv.lock）
uv sync --locked
```

## 项目结构

```
readwise-digest/
├── pyproject.toml          # 项目配置和依赖声明
├── uv.lock                 # 精确版本锁定（提交到 git）
├── .python-version          # Python 版本声明
├── .venv/                  # uv 自动创建的虚拟环境
├── .env                    # 环境变量（不提交到 git）
├── .env.example            # 环境变量模板
├── README.md
├── src/
│   ├── clients/
│   │   ├── llm_client.py       # LLM API 封装
│   │   └── readwise_client.py  # Readwise API 封装
│   ├── pipeline/
│   │   ├── filtering.py        # 过滤去重逻辑
│   │   └── ranking.py          # LLM 评分排序
│   ├── renderers/
│   │   └── markdown_renderer.py
│   ├── config.py               # 配置管理
│   ├── models.py               # 数据模型
│   └── main.py                 # CLI 入口
└── tests/
    ├── unit/                   # 单元测试
    └── integration/            # 集成测试
```

## 配置

编辑 `.env` 文件配置你的 API 密钥：

```env
# Readwise
READWISE_TOKEN=your_readwise_token

# LLM（MiniMax 示例）
LLM_API_KEY=your_minimax_api_key
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.5
```

其他配置选项见 `.env.example`。

## 为什么使用 uv？

本项目采用 **uv** 作为包管理工具，这是 2026 年 Python 生态的最佳实践：

- **速度**：比 pip 快 10-100 倍
- **自动虚拟环境管理**：无需手动 `source .venv/bin/activate`
- **原生 lockfile**：`uv.lock` 确保跨机器完全一致
- **零配置**：自动处理 Python 版本和虚拟环境

## 迁移自 pip

如果你熟悉传统的 pip + venv 工作流：

| 传统方式 | uv 方式 |
|---------|--------|
| `python -m venv .venv` | `uv sync`（自动创建） |
| `source .venv/bin/activate` | `uv run`（自动使用） |
| `pip install -r requirements.txt` | `uv sync` |
| `pip install package` | `uv add package` |
| `pip freeze > requirements.txt` | `uv lock` |

## CI/CD 最佳实践

在 CI/CD 流水线中使用严格模式：

```yaml
# GitHub Actions 示例
- name: Setup uv
  uses: astral-sh/setup-uv@v3

- name: Install dependencies
  run: uv sync --locked

- name: Run tests
  run: uv run pytest tests/unit -v
```

## 输出

日报生成后会保存到 `output/` 目录：

```
output/
├── readwise-digest-2026-03-19.md
└── readwise-digest-2026-03-19-test.md
```

## 扩展功能

- [ ] 邮件推送
- [ ] 企业微信/Webhook
- [ ] 历史记录去重（SQLite/Postgres）
- [ ] 定时调度

## License

MIT

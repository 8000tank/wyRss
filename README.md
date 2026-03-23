# Readwise 日报生成器

一个最小可用的纯 Python 工作流：从 `Readwise Reader` 拉取文章，用 `OpenAI` 兼容接口做摘要与评分，然后输出本地 `Markdown` 日报。

## 环境要求

- Python 3.12+（版本声明见 `.python-version`；若本机未安装，可用 `uv python install` 拉取）
- **[uv](https://docs.astral.sh/uv/)** — **请优先使用 uv** 管理本项目的依赖与运行命令
- `Readwise Reader` API Token
- `OpenAI` 兼容模型配置（智谱、MiniMax 等）

## 安装

### 1. 安装 uv（若尚未安装）

**优先安装 uv**，再克隆/进入本项目。官方文档：<https://docs.astral.sh/uv/getting-started/installation/>

常用方式：

**Linux / macOS：**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装完成后按提示将 `uv` 加入 `PATH`（脚本结尾一般会说明，例如重新打开终端或 `source` 其打印的配置文件）。

**macOS（Homebrew）：**

```bash
brew install uv
```

**Windows（PowerShell）：**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

验证：

```bash
uv --version
```

### 2. 安装本项目依赖

```bash
# 进入项目根目录（仓库名以你本地为准）
cd wyRss

# 创建虚拟环境并安装依赖（uv 会按 .python-version 选用 Python）
uv sync
```

**环境变量不是必须复制模板才能用。** 程序通过 `python-dotenv` 在项目目录下查找 `.env`：若存在则把其中的键加载到进程环境里；你也可以在 shell、IDE 或 CI 里直接导出同名变量，**不创建 `.env` 文件同样可以运行**。复制模板只是本地开发时比较方便：

```bash
# 可选：从模板生成 .env，再按需编辑
cp .env.example .env
```

## 快速开始

```bash
# 运行日报生成（自动使用 .venv）
uv run python -m src.main

# 或使用项目注册的命令（等价）
uv run readwise-digest
```

### 命令行参数（可选）

| 参数 | 说明 |
|------|------|
| `--hours N` | 覆盖统计窗口（小时），默认见 `.env` / `DIGEST_HOURS` |
| `--top-n N` | 覆盖最终入选篇数 |
| `--candidate-limit N` | 覆盖进入 LLM 打分的候选上限 |
| `--log-level` | `DEBUG` / `INFO` / `WARNING` / `ERROR`，默认 `INFO` |

示例：

```bash
uv run python -m src.main --hours 48 --top-n 15 --log-level INFO
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
项目根目录/
├── pyproject.toml          # 项目配置和依赖声明
├── uv.lock                 # 精确版本锁定（提交到 git）
├── .python-version         # Python 版本声明
├── .venv/                  # uv 自动创建的虚拟环境
├── .env                    # 本地环境变量（可选，不提交到 git）
├── .env.example            # 环境变量说明与模板
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

运行时统一从 **进程环境变量** 读取：`load_dotenv()` 会把项目目录下的 `.env` 合并进环境（默认**不会**用 `.env` 覆盖已在环境中设置的变量）。因此本地文件与 CI/系统导出变量两种方式都支持。

**必填（至少其一方式提供）：**

- `READWISE_TOKEN`
- `RSS_LLM_API_KEY`、`RSS_LLM_MODEL`

**LLM 相关命名（推荐）：**

```env
# Readwise
READWISE_TOKEN=your_readwise_token

# LLM（MiniMax 示例）
RSS_LLM_API_KEY=your_minimax_api_key
RSS_LLM_BASE_URL=https://api.minimaxi.com/v1
RSS_LLM_MODEL=MiniMax-M2.5
```

若未设置上述 `RSS_LLM_*`，程序会**回退**读取旧名：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，便于迁移旧 `.env`。

其余选项（时间窗口、候选数、输出目录等）见 `.env.example`；输出目录由 `DIGEST_OUTPUT_DIR` 控制，默认 `output/`。

## 为什么使用 uv？

本项目以 **uv** 为唯一推荐的工具链：

- **速度快**：依赖解析与安装显著快于传统方案
- **自动虚拟环境**：无需手动 `source .venv/bin/activate`
- **原生 lockfile**：`uv.lock` 保证各环境依赖版本一致
- **一条命令运行**：`uv run …` 始终在正确环境中执行

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

在流水线中通常用 **密钥仓库 / Environment** 注入 `READWISE_TOKEN`、`RSS_LLM_API_KEY` 等，无需提交 `.env`。

## 输出

成功运行后，日报写入 `DIGEST_OUTPUT_DIR`（默认 `output/`），文件名格式为：

```text
AI-digest_YYYYMMDD_HHMMSS.md
```

其中时间戳为 **UTC**，与日志中的生成时间一致。

## 扩展功能

- [ ] 邮件推送
- [ ] 企业微信/Webhook
- [ ] 历史记录去重（SQLite/Postgres）
- [ ] 定时调度

## License

MIT

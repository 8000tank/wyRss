#!/bin/bash
# wyRss 每日日报：生成 → 飞书文档 → 飞书消息推送
# 系统 cron 调用，所有路径使用绝对路径
set -euo pipefail

WYRSS_DIR="/root/code/wyRss"
source "$WYRSS_DIR/.env"
UV="/root/.local/bin/uv"
PYTHON="$WYRSS_DIR/.venv/bin/python"
LOG_FILE="$WYRSS_DIR/scripts/cron.log"
SEND_MSG="$WYRSS_DIR/scripts/send_feishu_msg.py"
FEISHU_USER="ou_999a6354b036a7ee70fbb2367d14f62c"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "========== 开始执行 =========="

cd "$WYRSS_DIR"

# Step 1: 生成日报 Markdown
log "[1/3] 生成日报 Markdown..."
if ! MD_FILE=$($UV run python -m src.main 2>>"$LOG_FILE" | tail -1); then
    log "[ERROR] 日报生成失败"
    exit 1
fi

# MD_FILE 应该是类似 output/AI-digest_20260401_092451.md 的路径
if [[ "$MD_FILE" != output/* ]]; then
    # 如果输出格式变了，尝试从 output 目录找最新文件
    MD_FILE=$(ls -t "$WYRSS_DIR"/output/AI-digest_*.md 2>/dev/null | head -1)
fi

if [[ -z "$MD_FILE" ]]; then
    log "[ERROR] 未找到生成的日报文件"
    exit 1
fi

# 确保是完整路径
[[ "$MD_FILE" != /* ]] && MD_FILE="$WYRSS_DIR/$MD_FILE"

log "[1/3] 日报文件: $MD_FILE"

# Step 2: 创建飞书文档
log "[2/3] 创建飞书文档..."
if ! DOC_OUTPUT=$($UV run python scripts/md_to_feishu.py "$MD_FILE" 2>>"$LOG_FILE"); then
    log "[ERROR] 飞书文档创建失败"
    exit 1
fi

# 从输出中提取文档链接
DOC_URL=$(echo "$DOC_OUTPUT" | grep -oP 'https://feishu\.cn/docx/\S+' | tail -1)
if [[ -z "$DOC_URL" ]]; then
    log "[ERROR] 未从输出中提取到文档链接"
    exit 1
fi

log "[2/3] 文档链接: $DOC_URL"

# Step 3: 提取标题并发送飞书消息
TITLE=$(head -1 "$MD_FILE" | sed 's/^#\s*//')
log "[3/4] 发送飞书消息: $TITLE"

$PYTHON "$SEND_MSG" --to "$FEISHU_USER" --title "$TITLE" --url "$DOC_URL" 2>>"$LOG_FILE"

# Step 4: 保存到 Get笔记 AI日报知识库
GETNOTE_SCRIPT="$WYRSS_DIR/scripts/save_to_getnote.py"
GETNOTE_TOPIC_ID="zJKeGA4Y"
log "[4/4] 保存到 Get笔记知识库..."
if ! GETNOTE_OUTPUT=$($UV run python "$GETNOTE_SCRIPT" "$MD_FILE" "$DOC_URL" "$GETNOTE_TOPIC_ID" 2>>"$LOG_FILE"); then
    log "[WARN] Get笔记保存失败: $GETNOTE_OUTPUT"
else
    log "[4/4] Get笔记保存成功: $GETNOTE_OUTPUT"
fi

log "========== 执行成功 =========="

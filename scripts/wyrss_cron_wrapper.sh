#!/bin/bash
# wyRss 日报 cron wrapper
# 串联生成 + 飞书文档创建，输出文档链接到 /tmp/wyrss_wyrss_cron_wrapper.sh
set -euo pipefail

RESULT_FILE="/tmp/wyrss_result.txt"
WYRSS_DIR="/root/code/wyRss"
UV="/root/.local/bin/uv"

echo "RESULT_FILE=$RESULT_FILE" > "$RESULT_FILE"
echo "---LOG_START---" >> "$RESULT_FILE"

cd "$WYRSS_DIR"

# Step 1: Generate digest
echo "[1/3] Generating digest..." >> "$RESULT_FILE"
MD_FILE=$($UV run python scripts/daily_digest_to_feishu.py 2>>"$RESULT_FILE") && echo "MD_FILE=$MD_FILE" >> "$RESULT_FILE"

# Step 2: Create Feishu document
echo "[2/3] Creating Feishu document..." >> "$RESULT_FILE"
DOC_URL=$($UV run python scripts/md_to_feishu.py "$MD_FILE" 2>>"$RESULT_FILE" | grep -oP 'https://feishu\.cn/docx/\S+') && echo "DOC_URL=$DOC_URL" >> "$RESULT_FILE"

# Step 3: Write final result
echo "---LOG_END---" >> "$RESULT_FILE"
echo "$DOC_URL"

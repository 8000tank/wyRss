#!/bin/bash
# 每日 AI 日报生成 → 飞书文档推送
# 由 cron 触发，每天 8:15 北京时间
# 
# 8:15 AM 北京时间 (CST, UTC+8) = 00:15 UTC
# Cron: 15 0 * * *

cd /root/code/wyRss
uv run python scripts/daily_digest_to_feishu.py >> /root/code/wyRss/scripts/cron.log 2>&1

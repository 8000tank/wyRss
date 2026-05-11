#!/usr/bin/env python3
"""发送飞书消息到指定用户"""
import requests
import json
import sys
import argparse
import time
import re

APP_ID = "cli_a909a5bfc7791bcc"
APP_SECRET = "WQv5m1lWWpIDhzioTajUgexhJPyIACES"
BASE_URL = "https://open.feishu.cn/open-apis"

def get_token():
    r = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET})
    d = r.json()
    if d["code"] != 0:
        raise Exception(f"token error: {d}")
    return d["tenant_access_token"]

def send_message(to_open_id, title, url):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    
    # 先创建聊天（P2P）
    r = requests.post(f"{BASE_URL}/im/v1/chats", headers=headers, json={
        "name": "日报推送",
        "chat_type": "p2p",
        "user_id_list": json.dumps([to_open_id]),
    })
    
    # 尝试直接发消息（如果已有 P2P 聊天）
    body = {
        "receive_id": to_open_id,
        "msg_type": "interactive",
        "content": json.dumps({
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📰 AI日报已生成"},
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📄 [{title}]({url})"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "打开文档"},
                            "type": "primary",
                            "url": url
                        }
                    ]
                }
            ]
        })
    }
    r = requests.post(f"{BASE_URL}/im/v1/messages?receive_id_type=open_id", headers=headers, json=body)
    d = r.json()
    if d.get("code") != 0:
        raise Exception(f"send message failed: {d}")
    print(f"✅ 消息发送成功: msg_id={d.get('data',{}).get('message_id')}")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="接收者的 open_id")
    parser.add_argument("--title", required=True, help="日报标题")
    parser.add_argument("--url", required=True, help="飞书文档链接")
    args = parser.parse_args()
    
    send_message(args.to, args.title, args.url)

if __name__ == "__main__":
    main()

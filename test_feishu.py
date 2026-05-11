#!/usr/bin/env python3
"""
Simple test script to check if Feishu API is working
"""
import requests
import json
import time

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

def test_create_doc():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    
    # Try to create a simple document
    r = requests.post(f"{BASE_URL}/docx/v1/documents", headers=headers, json={"title": "Test Document"})
    d = r.json()
    print(f"Create doc response: {d}")
    
    if d["code"] == 0:
        doc_id = d["data"]["document"]["document_id"]
        url = f"https://feishu.cn/docx/{doc_id}"
        print(f"✅ Test document created: {url}")
        return url
    else:
        print(f"❌ Failed to create document: {d}")
        return None

if __name__ == "__main__":
    test_create_doc()
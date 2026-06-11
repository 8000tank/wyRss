#!/usr/bin/env python3
"""Save wyRss daily digest to Get笔记 knowledge base."""
import json, sys, urllib.request, ssl, os

def load_config():
    with open(os.path.expanduser('~/.openclaw/openclaw.json')) as f:
        cfg = json.load(f)
    skill = cfg['skills']['entries']['getnote']
    api_key = skill['apiKey']
    client_id = skill['env']['GETNOTE_CLIENT_ID']
    return api_key, client_id

def api(method, path, body=None):
    api_key, client_id = load_config()
    ctx = ssl.create_default_context()
    url = f'https://openapi.biji.com{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', api_key)
    req.add_header('X-Client-ID', client_id)
    if body:
        req.add_header('Content-Type', 'application/json')
    resp = urllib.request.urlopen(req, context=ctx)
    return json.loads(resp.read().decode())

def main():
    md_file = sys.argv[1]  # e.g. output/AI-digest_20260611_085017.md
    topic_id = sys.argv[2] if len(sys.argv) > 2 else 'zJKeGA4Y'

    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract date from filename: AI-digest_YYYYMMDD_HHMMSS.md
    import re
    m = re.search(r'(\d{8})', md_file)
    date_str = m.group(1) if m else 'unknown'
    date_display = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'

    title = f'海心 AI日报 - {date_display}'
    tags = ['AI日报', date_display]

    # Step 1: Create note (plain_text, sync)
    print(f'[1/3] 创建笔记: {title}')
    result = api('POST', '/open/api/v1/resource/note/save', {
        'title': title,
        'content': content,
        'note_type': 'plain_text',
        'tags': tags,
    })
    if not result.get('success'):
        print(f'[ERROR] 创建失败: {result}')
        sys.exit(1)
    note_id = str(result['data']['id'])
    print(f'[1/3] 笔记ID: {note_id}')

    # Step 2: Add to knowledge base
    print(f'[2/3] 加入知识库: {topic_id}')
    result2 = api('POST', '/open/api/v1/resource/knowledge/note/batch-add', {
        'topic_id': topic_id,
        'note_ids': [note_id],
    })
    if not result2.get('success'):
        print(f'[WARN] 加入知识库失败: {result2}')
    else:
        print(f'[2/3] 已加入知识库')

    # Step 3: Add tags
    print(f'[3/3] 添加标签: {tags}')
    result3 = api('POST', '/open/api/v1/resource/note/tags/add', {
        'note_id': note_id,
        'tags': tags,
    })
    if not result3.get('success'):
        print(f'[WARN] 添加标签失败: {result3}')
    else:
        print(f'[3/3] 标签已添加')

    print(f'\n✅ 完成! 笔记ID: {note_id}, 标题: {title}')

if __name__ == '__main__':
    main()

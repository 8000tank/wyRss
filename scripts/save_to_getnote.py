#!/usr/bin/env python3
"""Save wyRss daily digest to Get笔记 knowledge base.

策略：先尝试存纯文本 Markdown，若遇到 405（WAF 拦截），
则降级为存链接笔记（指向飞书文档）。
"""
import json, sys, urllib.request, ssl, os, re, time


def load_config():
    api_key = ''
    client_id = ''

    # API Key 优先从 secrets.json 读取
    secrets_path = os.path.expanduser('~/.openclaw/secrets.json')
    if os.path.exists(secrets_path):
        with open(secrets_path, 'r') as f:
            secrets = json.load(f)
        entry = secrets.get('skills', {}).get('getnote', {})
        api_key = entry.get('apiKey', '')

    # Client ID 从 openclaw.json 读取
    config_path = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            cfg = json.load(f)
        entry = cfg.get('skills', {}).get('entries', {}).get('getnote', {})
        client_id = entry.get('env', {}).get('GETNOTE_CLIENT_ID', '')
        if not api_key:
            raw_key = entry.get('apiKey', '')
            if isinstance(raw_key, str) and raw_key.startswith('gk_'):
                api_key = raw_key

    return api_key, client_id


def api_post(path, body):
    """POST 请求，返回 (result_dict, http_status_code)。"""
    api_key, client_id = load_config()
    ctx = ssl.create_default_context()
    url = f'https://openapi.biji.com{path}'
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', api_key)
    req.add_header('X-Client-ID', client_id)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:300]
        return {'_http_error': True, 'code': e.code, 'body': body_text}, e.code


def save_plain_text(title, content, tags):
    """尝试存纯文本笔记，返回 note_id 或 None。"""
    result, code = api_post('/open/api/v1/resource/note/save', {
        'title': title,
        'content': content,
        'note_type': 'plain_text',
        'tags': tags,
    })
    if code == 405:
        print('[1/3] 纯文本被 WAF 拦截 (405)，降级为链接笔记')
        return None
    if code in (502, 503):
        print(f'[1/3] 纯文本创建失败 (HTTP {code}，服务端异常)，降级为链接笔记')
        return None
    if not result.get('success'):
        print(f'[WARN] 纯文本创建失败 (HTTP {code}): {result}')
        return None
    note_id = str(result['data']['id'])
    print(f'[1/3] 纯文本笔记已创建: {note_id}')
    return note_id


def save_link_note(title, feishu_url, tags):
    """存链接笔记（指向飞书文档），轮询直到完成，返回 note_id 或 None。"""
    result, code = api_post('/open/api/v1/resource/note/save', {
        'title': title,
        'content': f'完整内容见飞书文档链接。',
        'note_type': 'link',
        'link_url': feishu_url,
        'tags': tags,
    })
    if not result.get('success') or not result.get('data', {}).get('tasks'):
        print(f'[WARN] 链接笔记创建失败: {result}')
        return None
    task_id = result['data']['tasks'][0]['task_id']
    print(f'[1/3] 链接笔记任务已创建: {task_id}')

    # 轮询任务进度
    for i in range(12):
        time.sleep(5)
        poll_result, _ = api_post('/open/api/v1/resource/note/task/progress', {'task_id': task_id})
        status = poll_result.get('data', {}).get('status', 'unknown')
        if status == 'success':
            note_id = str(poll_result['data']['note_id'])
            print(f'[1/3] 链接笔记已创建: {note_id}')
            return note_id
        if status == 'failed':
            print(f'[WARN] 链接笔记处理失败: {poll_result}')
            return None
        print(f'[1/3] 等待处理中... ({i+1}/12)')
    print('[WARN] 链接笔记处理超时')
    return None


def add_to_kb(note_id, topic_id):
    """将笔记加入知识库。"""
    result2, _ = api_post('/open/api/v1/resource/knowledge/note/batch-add', {
        'topic_id': topic_id,
        'note_ids': [note_id],
    })
    if result2.get('success'):
        print(f'[2/3] 已加入知识库')
    else:
        print(f'[WARN] 加入知识库失败: {result2}')


def add_tags(note_id, tags):
    """为笔记添加标签。"""
    result3, _ = api_post('/open/api/v1/resource/note/tags/add', {
        'note_id': note_id,
        'tags': tags,
    })
    if result3.get('success'):
        print(f'[3/3] 标签已添加')
    else:
        print(f'[WARN] 添加标签失败: {result3}')


def main():
    md_file = sys.argv[1]
    feishu_url = sys.argv[2] if len(sys.argv) > 2 else ''
    topic_id = sys.argv[3] if len(sys.argv) > 3 else 'zJKeGA4Y'

    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract date from filename: AI-digest_YYYYMMDD_HHMMSS.md
    m = re.search(r'(\d{8})', md_file)
    date_str = m.group(1) if m else 'unknown'
    date_display = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'

    title = f'海心 AI日报 - {date_display}'
    tags = ['AI日报', date_display]

    # 尝试纯文本，405 时降级为链接笔记
    note_id = save_plain_text(title, content, tags)
    if note_id is None and feishu_url:
        note_id = save_link_note(title, feishu_url, tags)

    if note_id is None:
        print('[ERROR] 无法创建笔记')
        sys.exit(1)

    add_to_kb(note_id, topic_id)
    add_tags(note_id, tags)
    print(f'\n✅ 完成! 笔记ID: {note_id}, 标题: {title}')


if __name__ == '__main__':
    main()

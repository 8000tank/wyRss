import requests
import time

APP_ID = 'cli_a909a5bfc7791bcc'
APP_SECRET = 'WQv5m1lWWpIDhzioTajUgexhJPyIACES'
BASE_URL = 'https://open.feishu.cn/open-apis'

resp = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', 
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']

resp = requests.post(f'{BASE_URL}/docx/v1/documents', 
    headers={'Authorization': f'Bearer {token}'},
    json={'title': 'Quote Test3'})
doc_id = resp.json()['data']['document']['document_id']

# Try block_type 12 with key 'quote' and some variations
tests = [
    (12, 'quote', {'elements': [{'type': 'text_run', 'text_run': {'content': 'quote test'}}]}),
    (12, 'quote', {'elements': [{'type': 'text_run', 'text_run': {'content': 'quote test'}}], 'style': {'align': 1, 'folded': False}}),
    (12, 'blockquote', {'elements': [{'type': 'text_run', 'text_run': {'content': 'quote test'}}]}),
    (12, 'paragraph', {'elements': [{'type': 'text_run', 'text_run': {'content': 'quote test'}}]}),
]

for bt, key, content in tests:
    block = {'block_type': bt, key: content}
    resp = requests.post(
        f'{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
        headers={'Authorization': f'Bearer {token}'},
        json={'children': [block], 'index': 0}
    )
    try:
        result = resp.json()
        code = result.get('code', -1)
        if code == 0:
            print(f'✅ SUCCESS type={bt} key={key}')
            break
        else:
            print(f'❌ type={bt} key={key}: code={code} msg={result.get("msg","")[:50]}')
    except Exception as e:
        print(f'❌ type={bt} key={key}: {e}')
    time.sleep(0.5)

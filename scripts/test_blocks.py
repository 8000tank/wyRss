import requests

APP_ID = 'cli_a909a5bfc7791bcc'
APP_SECRET = 'WQv5m1lWWpIDhzioTajUgexhJPyIACES'
BASE_URL = 'https://open.feishu.cn/open-apis'

resp = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', 
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']

resp = requests.post(f'{BASE_URL}/docx/v1/documents', 
    headers={'Authorization': f'Bearer {token}'},
    json={'title': 'Heading Test3'})
doc_id = resp.json()['data']['document']['document_id']

# Test heading blocks
test_cases = [
    (3, 'heading1', 'Heading 1'),
    (4, 'heading2', 'Heading 2'),
    (5, 'heading3', 'Heading 3'),
]

for idx, (bt, key, text) in enumerate(test_cases):
    block = {
        'block_type': bt,
        key: {
            'elements': [{'type': 'text_run', 'text_run': {'content': text}}],
            'style': {'align': 1, 'folded': False}
        }
    }
    resp = requests.post(
        f'{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
        headers={'Authorization': f'Bearer {token}'},
        json={'children': [block], 'index': idx}
    )
    print(f'{key} (type={bt}): code={resp.json().get("code")} msg={resp.json().get("msg","")[:80]}')

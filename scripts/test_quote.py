import requests

APP_ID = 'cli_a909a5bfc7791bcc'
APP_SECRET = 'WQv5m1lWWpIDhzioTajUgexhJPyIACES'
BASE_URL = 'https://open.feishu.cn/open-apis'

resp = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', 
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']

resp = requests.post(f'{BASE_URL}/docx/v1/documents', 
    headers={'Authorization': f'Bearer {token}'},
    json={'title': 'Quote Test'})
doc_id = resp.json()['data']['document']['document_id']

# Try different quote-like block types
# Known types from Feishu: text=2, heading1=3, heading2=4, heading3=5
# bullet=9, ordered=10, code=12, quote=14, callout=15, etc.
test_types = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

for bt in test_types:
    block = {
        'block_type': bt,
        'text': {
            'elements': [{'type': 'text_run', 'text_run': {'content': f'quote test type={bt}'}}]
        }
    }
    resp = requests.post(
        f'{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
        headers={'Authorization': f'Bearer {token}'},
        json={'children': [block], 'index': 0}
    )
    code = resp.json().get('code', -1)
    label = '✅' if code == 0 else f'❌{code}'
    print(f'{label} type={bt}')
    if code == 0:
        print(f'  SUCCESS with key=text')
        break

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
    json={'title': 'Quote Test2'})
doc_id = resp.json()['data']['document']['document_id']

# Try quote block with key names for types 11-20
quote_keys = ['quote', 'blockquote', 'callout', 'code', 'bullet', 'ordered_list', 'list_item']

for bt in range(11, 21):
    for key in quote_keys:
        block = {
            'block_type': bt,
            key: {
                'elements': [{'type': 'text_run', 'text_run': {'content': f'quote test type={bt} key={key}'}}]
            }
        }
        resp = requests.post(
            f'{BASE_URL}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
            headers={'Authorization': f'Bearer {token}'},
            json={'children': [block], 'index': 0}
        )
        try:
            result = resp.json()
            code = result.get('code', -1)
        except:
            code = f'HTTP{resp.status_code}'
        if code == 0:
            print(f'✅ SUCCESS! type={bt} key={key}')
            break
        time.sleep(0.3)
    else:
        print(f'❌ type={bt}: all keys failed')

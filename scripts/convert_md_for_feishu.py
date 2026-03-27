"""把日报MD处理成feishu_doc友好的格式：表格转文本列表，清理HTML标签"""
import re, sys

def process(md):
    lines = md.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            result.append('')
            i += 1
            continue
        if line.startswith('|'):
            # 收集表格数据行（跳过分隔行）
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip('|').split('|')]
                if not all(re.match(r'^[-:]+$', c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                headers = rows[0]
                result.append('')
                for row_idx, row in enumerate(rows[1:], 1):
                    parts = [f'{headers[ci]}: {row[ci]}' if ci < len(headers) and ci < len(row) else str(row[ci]) for ci in range(len(row))]
                    result.append(' | '.join(parts))
                result.append('')
            continue
        line = re.sub(r'<a\s+name="[^"]*"></a>', '', line).strip()
        if line:
            result.append(line)
        i += 1
    return '\n'.join(result)

with open(sys.argv[1], 'r') as f:
    md = f.read()
out = process(md)
with open('/tmp/digest_final.md', 'w') as f:
    f.write(out)
print(f"done: {len(out)} chars")

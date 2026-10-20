"""collect.py 결과(details.json)로 전체 CSV와 이름 필터 결과(HTML 표 + 사진)를 만든다."""
import base64, csv, html, json, os, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else 'details.json'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'output'
CHARS = ('향', '미', '진')
POS = {'01': '대표', '02': '감사', '03': '이사', '04': '일반'}
GBN = {'1': '중개인', '2': '공인중개사', '3': '법인', '4': '중개보조원'}

os.makedirs(f'{OUT}/photos', exist_ok=True)

def photo_ext(raw):
    if raw[:3] == b'\xff\xd8\xff': return 'jpg'
    if raw[:4] == b'\x89PNG': return 'png'
    return 'gif'

rows = []
for d in json.load(open(SRC)):
    o = d['office']
    info = next((r for r in (d.get('getSvc0000049') or {}).get('result', [])
                 if r.get('RDEALER_NM') == o['rdealerNm']), {})
    tel = (info.get('TELNO') or o.get('telno') or '').replace('\n', ', ')
    base = {'등록번호': o['raRegno'], '상호': o['cmpNm'], '주소': info.get('JUSO') or o['address'],
            '전화번호': tel, '상태': o['stsGbn']}

    photo = ''
    for p in (d.get('getSvc0000051') or {}).get('result', []):
        if p.get('PUBLIC_GBN') == '0' and p.get('PHOTO'):
            raw = base64.b64decode(p['PHOTO'])
            photo = f"photos/{o['sysRegno']}.{photo_ext(raw)}"
            open(f'{OUT}/{photo}', 'wb').write(raw)

    rows.append({**base, '직위': '대표', '중개업자구분': info.get('RDEALER_GBN', ''),
                 '구분': '대표', '성명': o['rdealerNm'], '사진': photo})
    for m in (d.get('getSvc0000103') or {}).get('result', []):
        if m['V_POS_GBN'] == '01':
            continue
        gbn = GBN.get(m['V_RDEALER_GBN_P'], m['V_RDEALER_GBN_P'])
        rows.append({**base, '직위': POS.get(m['V_POS_GBN'], m['V_POS_GBN']), '중개업자구분': gbn,
                     '구분': '중개보조원' if gbn == '중개보조원' else '소속공인중개사',
                     '성명': m['V_RDEALER_NM'], '사진': ''})

fields = ['등록번호', '상호', '주소', '전화번호', '상태', '직위', '중개업자구분', '구분', '성명', '사진']
with open(f'{OUT}/서초동_중개법인_전체명단.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)

hits = [r for r in rows if any(c in r['성명'] for c in CHARS)]
with open(f'{OUT}/이름필터_결과.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(hits)

e = html.escape
trs = '\n'.join(
    '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><b>{}</b></td><td>{}</td></tr>'.format(
        f'<img src="{e(r["사진"])}" alt="{e(r["성명"])} 사진">' if r['사진']
        else '<span class="none">사진 비공개/미제공</span>',
        e(r['상호']), e(r['주소']), e(r['전화번호'] or '-'), e(r['성명']), e(r['구분']))
    for r in hits)
open(f'{OUT}/이름필터_결과.html', 'w').write(f'''<!doctype html><meta charset="utf-8">
<title>교대역 중개법인 명단</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--line:#ddd;--head:#f3f4f6;--muted:#888}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e8e8e8;--line:#333;--head:#22252b;--muted:#999}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;margin:16px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:middle}}
th{{background:var(--head)}}td:nth-child(5),td:nth-child(6){{white-space:nowrap}}img{{width:90px;display:block}}.none{{color:var(--muted);font-size:12px}}
</style>
<h2>교대역 인근(서초동) 중개법인 · 성명에 “향/미/진” 포함 ({len(hits)}명)</h2>
<p class="none">출처: 서울부동산정보광장 개업공인중개사 사무소 조회. 사진은 사이트가 공개하는 대표자 사진만 있으며, 소속공인중개사·중개보조원 사진은 사이트에서 제공하지 않습니다.</p>
<table><tr><th>사진</th><th>상호</th><th>주소</th><th>전화번호</th><th>성명</th><th>구분</th></tr>
{trs}</table>''')
print(f'offices={len({r["등록번호"] for r in rows})} people={len(rows)} hits={len(hits)} '
      f'hits_with_photo={sum(1 for r in hits if r["사진"])}')

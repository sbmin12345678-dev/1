import asyncio, json, random, base64, os, re
from playwright.async_api import async_playwright

URL = 'https://land.seoul.go.kr/land/broker/brokerInfo.do'
SEOCHO, SEOCHO_DONG = '11650', '1165010800'
ROADS = re.compile(r'(서초중앙로|서초대로|법원로|반포대로)(\d+길)?\s')
OUT = os.path.dirname(os.path.abspath(__file__))

async def pause():
    await asyncio.sleep(random.uniform(1.0, 2.0))

async def search(pg, keyword):
    await pg.select_option('#selectGubun', '2')
    await pg.fill('#searchContent', keyword)
    rows, page, total = [], 1, None
    while True:
        async with pg.expect_response(lambda r: 'searchBrokerList.do' in r.url) as ri:
            await pg.evaluate(f"searchBrokerList({page})")
        res = (await (await ri.value).json())['result']
        if not res:
            break
        total = res[0]['totalCount']
        rows += res
        print(f'  [{keyword}] page {page}: {len(res)} (total {total})', flush=True)
        if len(rows) >= total:
            break
        page += 1
        await pause()
    return rows

async def detail(pg, o):
    want = {'getSvc0000049': None, 'getSvc0000103': None, 'getSvc0000051': None}
    done = asyncio.Event()
    async def on_resp(r):
        for k in want:
            if k in r.url and want[k] is None:
                try: want[k] = await r.json()
                except Exception as e: want[k] = {'error': str(e)}
        if all(v is not None for v in want.values()):
            done.set()
    handler = lambda r: asyncio.ensure_future(on_resp(r))
    pg.on('response', handler)
    args = [o['landCd'], o['sggCd'], o['raRegno'], o['cmpNm'], o['sggNm'], o['rdealerNm'],
            o['sysRegno'], o['exclncYn'], o['elctrnCntrctYn']]
    await pg.evaluate("a => fnDetail(...a)", args)
    try:
        await asyncio.wait_for(done.wait(), 30)
    except asyncio.TimeoutError:
        print('  timeout on', o['cmpNm'])
    await pg.wait_for_timeout(800)
    pg.remove_listener('response', handler)
    return want

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium', args=['--no-sandbox'])
        pg = await b.new_page(viewport={'width': 1400, 'height': 1000})
        await pg.goto(URL, wait_until='load', timeout=60000)
        await pg.wait_for_function("document.querySelectorAll('#selectSigungu option').length > 5")
        await pg.select_option('#selectSigungu', SEOCHO)
        await pause()

        if os.path.exists(f'{OUT}/search_all.json'):
            allrows = {r['sysRegno']: r for r in json.load(open(f'{OUT}/search_all.json'))}
        else:
            allrows = {}
            for kw in ['중개법인', '부동산중개']:
                for r in await search(pg, kw):
                    allrows.setdefault(r['sysRegno'], r)
                await pause()
            json.dump(list(allrows.values()), open(f'{OUT}/search_all.json', 'w'), ensure_ascii=False, indent=1)
        targets = [r for r in allrows.values() if r['stsGbn'] == '영업중' and r['bjdongCd'] == SEOCHO_DONG
                   and ROADS.search(r['address'])]
        print(f'unique offices: {len(allrows)}, 영업중+서초동+교대역권 도로: {len(targets)}', flush=True)

        details = json.load(open(f'{OUT}/details.json')) if os.path.exists(f'{OUT}/details.json') else []
        details = [d for d in details if ROADS.search(d['office']['address'])]
        have = {d['office']['sysRegno'] for d in details}
        for i, o in enumerate(targets, 1):
            if o['sysRegno'] in have:
                continue
            d = await detail(pg, o)
            details.append({'office': o, **d})
            print(f'  detail {i}/{len(targets)} {o["cmpNm"]}', flush=True)
            json.dump(details, open(f'{OUT}/details.json', 'w'), ensure_ascii=False)
            await pause()
        await b.close()

asyncio.run(main())

#!/usr/bin/env python3
"""아일랜드이너프 인스타그램 카드뉴스 자동 업로드.

하루 한 번 실행하면:
  1. 홈페이지에서 지점 정보 · 요금 · 사진 목록을 읽고
  2. ai-photos/ 폴더의 AI 사진(있으면 우선)과 홈페이지 파티 사진으로 카드 7장을 만들고
  3. cards/<날짜>/ 에 저장해 GitHub에 올린 뒤
  4. 인스타그램에 캐러셀(여러 장) 게시물로 올립니다.

사용법:
  python3 tools/daily_post.py                 # 오늘 날짜로 제작 + 업로드 + 게시
  python3 tools/daily_post.py --no-publish    # 제작 + GitHub 업로드만 (인스타그램 게시 안 함)
  python3 tools/daily_post.py --local         # 카드만 만들어 보기 (GitHub · 인스타그램 모두 안 함)
  python3 tools/daily_post.py --date 2026-12-01

ai-photos/ 파일 이름 규칙: 지점 이름으로 시작 (예: 양재_생일.png, 도산_브라이덜.jpg)
"""
import argparse, datetime as dt, glob, json, os, subprocess, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://islandenoughpartyroom.com'
RAW = 'https://raw.githubusercontent.com/islandenough/islandenough-photos/main'
GRAPH = 'https://graph.facebook.com/v23.0'
IG_USER = '17841408375893159'  # @islandenough
TOKEN = os.environ.get('META_TOKEN', 'proxy-injected')  # 실제 토큰은 네트워크 프록시가 넣어 줍니다
KST = ZoneInfo('Asia/Seoul')
CACHE = os.path.join(ROOT, '.cache')

W, H = 1080, 1350
GREEN = (20, 58, 44); MINT = (170, 230, 200); CREAM = (250, 247, 240); GOLD = (236, 196, 110)

# 운영 지점 (이태원점은 폐업으로 제외). id는 홈페이지 사진 폴더 이름.
BRANCHES = [
    dict(id='yangjae', name='양재점', key='양재', loc='양재역 1번 출구 도보 3분', cap='최대 40명 · 실내 30평 + 테라스',
         feats=['120인치 빔프로젝터 · 미러볼 클럽 조명', '다트 · 미니 당구대 · 피아노', '와인냉장고 · 테라스 흡연 공간'], tags=['양재파티룸']),
    dict(id='yeoksam', name='역삼점', key='역삼', loc='선릉역 5번 출구 도보 5분', cap='최대 72명 · 약 40평 (최대 규모)',
         feats=['회사 송년회 · 대규모 단체 모임', '100인치 빔프로젝터 · 미니 당구대', '매장 내 남녀 화장실 구분'], tags=['역삼파티룸', '선릉파티룸']),
    dict(id='dosan', name='도산공원점', key='도산', loc='압구정로데오역 5번 출구 도보 5분', cap='최대 30명 · 약 25평',
         feats=['섬을 닮은 감성 인테리어 · 포토존', '120인치 빔프로젝터', '발렛 주차 가능 (대당 2만원)'], tags=['도산공원파티룸', '압구정파티룸']),
    dict(id='suyu', name='수유점', key='수유', loc='수유역 8번 출구 도보 5분', cap='최대 36명 · 약 35평',
         feats=['LG 86인치 4K TV (넷플릭스·유튜브)', '비밀의 방 2개 + 부엌(인덕션)', '강북 모임은 여기서!'], tags=['수유파티룸', '강북파티룸']),
    dict(id='gangnam', name='강남점', key='강남', loc='강남역 1번 출구 도보 5분', cap='강남 한복판 · 초역세권 파티룸',
         feats=['우리 일행만 쓰는 단독 대관', '생일 · 동창회 · 회사 모임까지', '퇴근 후 바로 모이기 좋은 위치'], tags=['강남파티룸', '강남역파티룸'],
         price='요금 · 예약 문의는 프로필 링크'),
]

# 날마다 바뀌는 주제 (날짜 순서대로 돌아감)
THEMES = [
    dict(badge='송년회 특집', title='올해 송년회,\n어디서 할까?', words=['송년'],
         intro='🎄 올해 송년회, 아직 장소 못 정하셨다면', tags=['송년회장소', '송년회', '회사송년회']),
    dict(badge='크리스마스 파티', title='크리스마스,\n우리끼리 파티룸', words=['크리스마스', '성탄'],
         intro='🎅 올 크리스마스는 우리끼리 단독 파티룸에서', tags=['크리스마스파티', '크리스마스파티룸']),
    dict(badge='생일파티', title='생일파티,\n제대로 해 볼까?', words=['생일'],
         intro='🎂 친구 생일, 이번엔 제대로 축하해 주세요', tags=['생일파티', '생일파티장소']),
    dict(badge='브라이덜샤워', title='브라이덜샤워,\n인생샷 남기기', words=['브라이덜', '신부'],
         intro='👰 예비 신부를 위한 특별한 하루', tags=['브라이덜샤워', '브라이덜샤워장소']),
    dict(badge='워크샵 · 단체모임', title='팀 워크샵,\n회의실 말고 여기', words=['워크샵', '회사', '세미나'],
         intro='💼 회의실 대신, 팀이 진짜 친해지는 공간', tags=['워크샵장소', '단체모임장소', '세미나장소']),
    dict(badge='동창 · 가족 모임', title='오랜만의 모임,\n편하게 우리끼리', words=['동창', '가족', '모임'],
         intro='🥂 오랜만에 다 같이 모이는 날', tags=['동창회장소', '가족모임장소', '연말모임']),
    dict(badge='연말 파티', title='연말 모임,\n어디서 할까?', words=['파티', '연말'],
         intro='✨ 한 해를 마무리하는 우리만의 파티', tags=['연말파티', '연말모임장소']),
]
COMMON_TAGS = ['아일랜드이너프', '서울파티룸', '강남파티룸', '파티룸', '대관', '단독대관']


def log(*a):
    print(*a, flush=True)


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def font(weight, size):
    return ImageFont.truetype(os.path.join(ROOT, 'tools', 'fonts', f'Pretendard-{weight}.otf'), size)


def fetch_photo(path):
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, path.replace('/', '_'))
    if not os.path.exists(fn):
        urllib.request.urlretrieve(f'{SITE}/photos/{path}', fn)
    return fn


def crop(fn, w, h):
    im = Image.open(fn).convert('RGB'); r = w / h; iw, ih = im.size
    if iw / ih > r:
        nw = int(ih * r); im = im.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / r); im = im.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    return im.resize((w, h), Image.LANCZOS)


def shade(im, top, bot, alpha, reverse=False):
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for y in range(top, bot):
        t = (y - top) / (bot - top)
        a = int(alpha * ((1 - t) ** 1.5 if reverse else t ** 1.3))
        d.line([(0, y), (im.width, y)], fill=(8, 24, 18, a))
    return Image.alpha_composite(im.convert('RGBA'), ov)


def header(d, i, n):
    d.text((60, 60), 'ISLAND ENOUGH', font=font('Bold', 30), fill='white')
    d.text((W - 60, 60), f'{i:02d} / {n:02d}', font=font('SemiBold', 30), fill='white', anchor='ra')


def ai_badge(d, x, y):
    d.rounded_rectangle([x - 210, y - 44, x, y], radius=22, fill=(0, 0, 0))
    d.text((x - 105, y - 22), 'AI 연출 이미지', font=font('SemiBold', 24), fill='white', anchor='mm')


def pick_photos(day, photo_index):
    """지점마다 사진 1장: ai-photos 의 해당 지점 사진을 우선, 없으면 홈페이지 파티 사진."""
    theme = THEMES[day % len(THEMES)]
    ai_files = sorted(glob.glob(os.path.join(ROOT, 'ai-photos', '*')))
    ai_files = [f for f in ai_files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    out = {}
    for b in BRANCHES:
        mine = [f for f in ai_files if os.path.basename(f).startswith(b['key'])]
        themed = [f for f in mine if any(w in os.path.basename(f) for w in theme['words'])]
        pool = themed or mine
        if pool:
            out[b['id']] = (pool[day % len(pool)], True)
            continue
        party = [p for p in photo_index.get(b['id'], {}).get('party', []) if p[1] / p[2] >= 1.25]
        p = party[(day * 3 + len(b['id'])) % len(party)]
        out[b['id']] = (fetch_photo(p[0]), False)
    return out


def price_line(b, cfg, date):
    if b.get('price'):
        return b['price']
    c = next(x for x in cfg['branches'] if x['id'] == b['id'])
    peak = date.month in cfg.get('peakMonths', [])
    night = c['prices']['peak' if peak else 'normal']['night'][0]  # 월~목 나이트
    return f'{date.month}월 평일 나이트 {night // 10000}만원~'


def make_cards(date, outdir):
    cfg = get_json(f'{SITE}/api/config')
    photo_index = get_json(f'{SITE}/photos/index.json')
    day = date.toordinal()
    theme = THEMES[day % len(THEMES)]
    photos = pick_photos(day, photo_index)
    os.makedirs(outdir, exist_ok=True)
    n = len(BRANCHES) + 2

    # 1. 표지: 그날 첫 지점 사진
    cover_b = BRANCHES[day % len(BRANCHES)]
    fn, is_ai = photos[cover_b['id']]
    im = shade(shade(crop(fn, W, H), 380, H, 250), 0, 170, 170, reverse=True)
    d = ImageDraw.Draw(im); header(d, 1, n)
    bw = int(d.textlength(theme['badge'], font=font('Bold', 32))) + 60
    d.rounded_rectangle([60, 760, 60 + bw, 820], radius=30, fill=GOLD)
    d.text((60 + bw // 2, 790), theme['badge'], font=font('Bold', 32), fill=GREEN, anchor='mm')
    d.text((60, 850), theme['title'], font=font('ExtraBold', 108), fill='white', spacing=14)
    d.text((60, 1120), f'서울 {len(BRANCHES)}개 지점 · 단독 대관 파티룸 한눈에 보기', font=font('Medium', 38), fill=MINT)
    d.text((60, 1230), '옆으로 넘겨 보세요  →', font=font('SemiBold', 34), fill='white')
    if is_ai: ai_badge(d, W - 60, 1270)
    im.convert('RGB').save(os.path.join(outdir, '01.jpg'), quality=90)

    # 2~6. 지점 카드
    for k, b in enumerate(BRANCHES, start=2):
        fn, is_ai = photos[b['id']]
        im = Image.new('RGB', (W, H), CREAM); im.paste(crop(fn, W, 720), (0, 0))
        im = shade(shade(im, 420, 720, 170), 0, 170, 170, reverse=True)
        d = ImageDraw.Draw(im); header(d, k, n)
        d.text((60, 600), b['name'], font=font('ExtraBold', 96), fill='white', anchor='ls')
        d.text((60, 660), b['loc'], font=font('SemiBold', 36), fill=MINT, anchor='ls')
        if is_ai: ai_badge(d, W - 40, 700)
        y = 780
        d.text((60, y), b['cap'], font=font('Bold', 44), fill=GREEN); y += 90
        for f in b['feats']:
            d.ellipse([62, y + 14, 80, y + 32], fill=(46, 140, 100))
            d.text((100, y), f, font=font('Medium', 38), fill=(40, 48, 44)); y += 70
        d.rounded_rectangle([60, 1150, W - 60, 1270], radius=28, fill=GREEN)
        d.text((W // 2, 1210), price_line(b, cfg, date), font=font('Bold', 44), fill=GOLD, anchor='mm')
        im.convert('RGB').save(os.path.join(outdir, f'{k:02d}.jpg'), quality=90)

    # 마지막: 예약 안내 (표지와 다른 지점 사진)
    last_b = BRANCHES[(day + 2) % len(BRANCHES)]
    fn, is_ai = photos[last_b['id']]
    im = shade(shade(crop(fn, W, H), 300, H, 250), 0, 170, 170, reverse=True)
    d = ImageDraw.Draw(im); header(d, n, n)
    d.text((60, 760), '연말 모임은\n아일랜드이너프\n파티룸에서', font=font('ExtraBold', 96), fill='white', spacing=12)
    d.text((60, 1090), '· 음식·주류·배달 자유 반입   · 공간 전체 단독 이용', font=font('Medium', 34), fill=MINT)
    d.text((60, 1140), '· 평일(월~목) 할인   · 주말은 빠르게 마감 중', font=font('Medium', 34), fill=MINT)
    d.rounded_rectangle([60, 1210, W - 60, 1300], radius=45, fill=GOLD)
    d.text((W // 2, 1255), '예약  islandenoughpartyroom.com', font=font('Bold', 40), fill=GREEN, anchor='mm')
    if is_ai: ai_badge(d, W - 60, 740)
    im.convert('RGB').save(os.path.join(outdir, f'{n:02d}.jpg'), quality=90)

    caption = make_caption(theme, cfg, date, any(v[1] for v in photos.values()))
    with open(os.path.join(outdir, 'caption.txt'), 'w', encoding='utf-8') as f:
        f.write(caption)
    return n, caption


def make_caption(theme, cfg, date, has_ai):
    lines = [theme['intro'], '아일랜드이너프 서울 5개 지점을 한눈에 비교해 보세요 👉', '']
    for b in BRANCHES:
        lines.append(f"📍 {b['name']} | {b['loc']} | {b['cap']}")
    lines += ['',
              '✔ 예약한 시간 동안 공간 전체를 우리 일행만 단독 이용',
              '✔ 음식 · 주류 · 배달 자유롭게 반입',
              '✔ 빔프로젝터 · 무선 마이크 · 보드게임 무료',
              '✔ 평일(월~목) 할인 · 주말은 빠르게 마감 중',
              '',
              '연말 모임은 아일랜드이너프 파티룸에서 🥂',
              '예약은 프로필 링크 → islandenoughpartyroom.com']
    if has_ai:
        lines += ['', '※ 일부 사진은 실제 매장 사진을 바탕으로 만든 AI 연출 이미지입니다.']
    tags = list(dict.fromkeys(COMMON_TAGS + theme['tags'] + [t for b in BRANCHES for t in b['tags']]))[:28]
    lines += ['', ' '.join('#' + t for t in tags)]
    return '\n'.join(lines)


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], check=True, capture_output=True, text=True).stdout


def push_cards(date_str):
    git('pull', '--rebase', '--autostash', 'origin', 'main')
    git('add', f'cards/{date_str}')
    if not git('status', '--porcelain', f'cards/{date_str}').strip():
        log('cards already committed'); return
    git('commit', '-m', f'카드뉴스 {date_str}')
    for i in range(4):
        try:
            git('push', 'origin', 'HEAD:main'); log('pushed to GitHub'); return
        except subprocess.CalledProcessError as e:
            log('push failed, retrying:', e.stderr.strip()[-200:]); time.sleep(2 ** (i + 1))
            git('pull', '--rebase', 'origin', 'main')
    raise SystemExit('GitHub 업로드 실패')


def graph(method, path, **params):
    data = urllib.parse.urlencode(params).encode() if method == 'POST' else None
    url = f'{GRAPH}/{path}' + ('' if method == 'POST' else '?' + urllib.parse.urlencode(params))
    req = urllib.request.Request(url, data=data, method=method, headers={'Authorization': f'Bearer {TOKEN}'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Instagram API 오류 {e.code}: {e.read().decode()[:500]}')


def wait_ready(cid):
    for _ in range(30):
        s = graph('GET', cid, fields='status_code,status')
        if s.get('status_code') == 'FINISHED': return
        if s.get('status_code') == 'ERROR': raise SystemExit(f'Instagram 처리 오류: {s}')
        time.sleep(4)
    raise SystemExit('Instagram 처리 시간 초과')


def wait_raw(url):
    for _ in range(30):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as r:
                if r.status == 200: return
        except Exception:
            pass
        time.sleep(5)
    raise SystemExit(f'이미지 주소에 접근할 수 없음: {url}')


def publish(date_str, n, caption):
    urls = [f'{RAW}/cards/{date_str}/{i:02d}.jpg' for i in range(1, n + 1)]
    wait_raw(urls[-1])
    children = []
    for u in urls:
        c = graph('POST', f'{IG_USER}/media', image_url=u, is_carousel_item='true')
        children.append(c['id'])
    for c in children: wait_ready(c)
    car = graph('POST', f'{IG_USER}/media', media_type='CAROUSEL', children=','.join(children), caption=caption)
    wait_ready(car['id'])
    res = graph('POST', f'{IG_USER}/media_publish', creation_id=car['id'])
    info = graph('GET', res['id'], fields='permalink,timestamp')
    log('PUBLISHED', info.get('permalink'))
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', help='YYYY-MM-DD (기본: 오늘, 한국 시간)')
    ap.add_argument('--no-publish', action='store_true')
    ap.add_argument('--local', action='store_true')
    ap.add_argument('--force', action='store_true', help='이미 게시한 날짜도 다시 게시')
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(KST).date()
    ds = date.isoformat(); outdir = os.path.join(ROOT, 'cards', ds)
    done = os.path.join(outdir, 'posted.json')
    if os.path.exists(done) and not a.force:
        log('이미 게시됨:', json.load(open(done)).get('permalink')); return
    n, caption = make_cards(date, outdir)
    log(f'cards: {outdir} ({n}장)')
    if a.local: return
    push_cards(ds)
    if a.no_publish: return
    info = publish(ds, n, caption)
    with open(done, 'w') as f: json.dump(info, f, ensure_ascii=False)
    git('add', done); git('commit', '-m', f'게시 완료 {ds}')
    try: git('push', 'origin', 'HEAD:main')
    except subprocess.CalledProcessError:
        git('pull', '--rebase', 'origin', 'main'); git('push', 'origin', 'HEAD:main')


if __name__ == '__main__':
    main()

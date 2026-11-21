#!/usr/bin/env python3
"""아일랜드이너프 인스타그램 카드뉴스 자동 업로드.

하루 한 번 실행하면:
  1. 홈페이지에서 지점 정보 · 요금 · 사진 목록을 읽고
  2. ai-photos/ 폴더의 AI 사진(있으면 우선)과 홈페이지 파티 사진으로 카드를 만들고
     (표지는 늘 같은 틀, 안쪽은 날마다 형식 순환: 지점 비교 → 한 지점 집중 → 파티 사진 모음)
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
    dict(id='yeoksam', name='역삼점', key='역삼', loc='선릉역 5번 출구 도보 5분', cap='최대 72명 · 약 40평',
         feats=['회사 송년회 · 대규모 단체 모임', '100인치 빔프로젝터 · 미니 당구대', '매장 내 남녀 화장실 구분'], tags=['역삼파티룸', '선릉파티룸']),
    dict(id='dosan', name='도산공원점', key='도산', loc='압구정로데오역 5번 출구 도보 5분', cap='최대 30명 · 약 25평',
         feats=['섬을 닮은 감성 인테리어 · 포토존', '120인치 빔프로젝터', '발렛 주차 가능 (대당 2만원)'], tags=['도산공원파티룸', '압구정파티룸']),
    dict(id='suyu', name='수유점', key='수유', loc='수유역 8번 출구 도보 5분', cap='최대 36명 · 약 35평',
         feats=['LG 86인치 4K TV (넷플릭스·유튜브)', '비밀의 방 2개 + 부엌(인덕션)', '강북 모임은 여기서!'], tags=['수유파티룸', '강북파티룸']),
    dict(id='gangnam', name='강남점', key='강남', loc='역삼역 4번 출구 약 300m', cap='최대 78명 · 약 50평 (최대 규모)',
         feats=['120인치 풀HD 빔프로젝터 · JBL 스피커', '아일랜드바 · 소파 라운지', '디제잉 장비 연결 가능'], tags=['강남파티룸', '역삼역파티룸']),
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


IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp')


def branch_pool(b, photo_index, theme, day):
    """한 지점의 사진 목록 (fn, AI여부). AI 사진(그날 주제에 맞는 것 먼저) → 홈페이지 파티 사진 순."""
    ai = sorted(f for f in glob.glob(os.path.join(ROOT, 'ai-photos', '*'))
                if f.lower().endswith(IMG_EXT) and os.path.basename(f).startswith(b['key']))
    themed = [f for f in ai if any(w in os.path.basename(f) for w in theme['words'])]
    rest = [f for f in ai if f not in themed]
    if rest: rest = rest[day % len(rest):] + rest[:day % len(rest)]
    party = [p for p in photo_index.get(b['id'], {}).get('party', []) if p[1] / p[2] >= 1.25]
    if party:
        k = (day * 3 + len(b['id'])) % len(party); party = party[k:] + party[:k]
    return [(f, True) for f in themed + rest] + [(('site', p[0]), False) for p in party]


def load(item):
    fn, is_ai = item
    if isinstance(fn, tuple): fn = fetch_photo(fn[1])
    return fn, is_ai


def price_line(b, cfg, date):
    import content
    m = content.target_month(date)
    return f"{m}월 월~목·일 나이트 {content.man(content.table_price(cfg, b['id'], m, 'night', 0))}~"


# ---- 카드 종류 ----
def card_cover(item, i, n, badge, title, sub):
    """표지: 모든 게시물이 같은 틀 (피드 통일감)."""
    fn, is_ai = load(item)
    im = shade(shade(crop(fn, W, H), 380, H, 250), 0, 170, 170, reverse=True)
    d = ImageDraw.Draw(im); header(d, i, n)
    bw = int(d.textlength(badge, font=font('Bold', 32))) + 60
    d.rounded_rectangle([60, 760, 60 + bw, 820], radius=30, fill=GOLD)
    d.text((60 + bw // 2, 790), badge, font=font('Bold', 32), fill=GREEN, anchor='mm')
    d.text((60, 850), title, font=font('ExtraBold', 108), fill='white', spacing=14)
    d.text((60, 1120), sub, font=font('Medium', 38), fill=MINT)
    d.text((60, 1230), '옆으로 넘겨 보세요  →', font=font('SemiBold', 34), fill='white')
    if is_ai: ai_badge(d, W - 60, 1270)
    return im


def card_branch(item, i, n, b, cfg, date):
    fn, is_ai = load(item)
    im = Image.new('RGB', (W, H), CREAM); im.paste(crop(fn, W, 720), (0, 0))
    im = shade(shade(im, 420, 720, 170), 0, 170, 170, reverse=True)
    d = ImageDraw.Draw(im); header(d, i, n)
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
    return im


def card_photo(item, i, n, label=None):
    """사진만 크게. 아래에 작은 지점 이름표."""
    fn, is_ai = load(item)
    im = shade(crop(fn, W, H), 0, 170, 150, reverse=True)
    if label: im = shade(im, H - 260, H, 200)
    d = ImageDraw.Draw(im); header(d, i, n)
    if label:
        d.text((60, H - 70), label, font=font('Bold', 46), fill='white', anchor='ls')
    if is_ai: ai_badge(d, W - 60, H - 50)
    return im


def card_cta(item, i, n):
    fn, is_ai = load(item)
    im = shade(shade(crop(fn, W, H), 300, H, 250), 0, 170, 170, reverse=True)
    d = ImageDraw.Draw(im); header(d, i, n)
    d.text((60, 760), '연말 모임은\n아일랜드이너프\n파티룸에서', font=font('ExtraBold', 96), fill='white', spacing=12)
    d.text((60, 1080), '· 음식·술·배달 자유 반입   · 콜키지 0원', font=font('Medium', 34), fill=MINT)
    d.text((60, 1128), '· 공간 전체 단독 이용   · 월~목·일요일 밤이 더 저렴', font=font('Medium', 34), fill=MINT)
    d.rounded_rectangle([60, 1190, W - 60, 1270], radius=40, fill=GOLD)
    d.text((W // 2, 1230), '프로필 링크에서 바로 예약하기', font=font('ExtraBold', 40), fill=GREEN, anchor='mm')
    d.text((W // 2, 1308), 'islandenoughpartyroom.com', font=font('Bold', 30), fill='white', anchor='mm')
    if is_ai: ai_badge(d, W - 60, 740)
    return im


# ---- 게시물 형식 (날마다 순환) ----
FORMATS = ['compare', 'branch', 'gallery', 'saving']

# 비용 비교 콘텐츠: 밖에서 하는 회식 (서울 강남권 예시 금액, 20명 기준)
SAVING_PEOPLE = 20
OUTSIDE = [  # (단계, 내용, 1인 예시 금액)
    ('1차 고깃집', '삼겹살·목살 + 소주·맥주 + 식사', 50000),
    ('2차 맥주집', '생맥주 + 안주', 25000),
    ('3차 노래방', '대형룸 2시간 + 음료', 7500),
]
INSIDE_FOOD = 25000   # 배달 음식 1인 예시 (족발·보쌈·치킨·피자 등)
INSIDE_DRINK = 10000  # 마트 주류 1인 예시


def won_k(v):
    return f'{v:,}원'


def text_card(i, n, title, rows, total_label, total, note=None, accent=GREEN):
    im = Image.new('RGBA', (W, H), CREAM)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=GREEN); header(d, i, n)
    d.text((60, 250), title, font=font('ExtraBold', 76), fill=accent)
    y = 400
    for name, desc, amt in rows:
        d.text((60, y), name, font=font('Bold', 46), fill=(30, 40, 35))
        d.text((W - 60, y), amt, font=font('Bold', 46), fill=(30, 40, 35), anchor='ra')
        d.text((60, y + 62), desc, font=font('Medium', 32), fill=(110, 120, 115))
        y += 150
        d.line([(60, y - 30), (W - 60, y - 30)], fill=(220, 215, 205), width=2)
    d.rounded_rectangle([60, 1060, W - 60, 1200], radius=28, fill=accent)
    d.text((100, 1130), total_label, font=font('Bold', 42), fill='white', anchor='lm')
    d.text((W - 100, 1130), total, font=font('ExtraBold', 56), fill=GOLD, anchor='rm')
    if note:
        d.text((60, 1250), note, font=font('Medium', 26), fill=(130, 135, 130))
    return im


def saving_numbers(cfg, date, branch_id='yeoksam'):
    c = next(x for x in cfg['branches'] if x['id'] == branch_id)
    peak = date.month in cfg.get('peakMonths', [])
    room = c['prices']['peak' if peak else 'normal']['night'][0]
    extra = max(0, SAVING_PEOPLE - cfg['baseHeadcount']) * cfg['extraPerPerson']
    out_rows = [(a, b, v * SAVING_PEOPLE) for a, b, v in OUTSIDE]
    in_rows = [('파티룸 대관', f"{date.month}월 평일 나이트 5시간 · 단독 이용", room),
               ('인원 추가', f"{cfg['baseHeadcount']}인 초과 {SAVING_PEOPLE - cfg['baseHeadcount']}명 × {cfg['extraPerPerson']:,}원", extra),
               ('배달 음식', '족발·보쌈·치킨·피자 등', INSIDE_FOOD * SAVING_PEOPLE),
               ('주류', '마트에서 구입', INSIDE_DRINK * SAVING_PEOPLE)]
    return out_rows, in_rows


def make_cards(date, outdir, fmt=None, which=None):
    """요일별 콘텐츠(tools/content.py)로 카드를 만든다. fmt='main' 은 대표 캐러셀(tools/main_ad.py)."""
    import content, main_ad
    cfg = get_json(f'{SITE}/api/config')
    photo_index = get_json(f'{SITE}/photos/index.json')
    day = date.toordinal()
    fmt = fmt or content.plan(date)
    theme = THEMES[day % len(THEMES)]
    pools = {b['id']: branch_pool(b, photo_index, theme, day) for b in BRANCHES}
    week = day // 7
    focus = BRANCHES[week % len(BRANCHES)]
    # 표지는 AI 사진이 있는 지점을 우선 (요일마다 돌아가며)
    with_ai = [b for b in BRANCHES if any(x[1] for x in pools[b['id']])]
    lead = with_ai[day % len(with_ai)] if with_ai else BRANCHES[day % len(BRANCHES)]
    used = []

    def take(b, k=0):
        item = pools[b['id']][min(k, len(pools[b['id']]) - 1)]
        used.append(item); return item

    src = with_ai or BRANCHES

    def strip(j):  # 글 카드 아래 사진: AI 사진이 있는 지점을 돌아가며
        return take(src[j % len(src)], 1 + j // len(src))

    ctx = dict(cfg=cfg, date=date, day=day, take=take, focus=focus, lead=lead, strip=strip, photo_index=photo_index)
    if fmt == 'main':  # 실제 사진만 사용, 주마다 사진 묶음 교체
        slides, cap, tags = main_ad.build(ctx, week if which is None else which)
    else:
        slides, cap, tags = content.build(fmt, ctx)

    os.makedirs(outdir, exist_ok=True)
    for old in glob.glob(os.path.join(outdir, '*.jpg')): os.remove(old)
    n = len(slides)
    for i, make in enumerate(slides, start=1):
        make(i, n).convert('RGB').save(os.path.join(outdir, f'{i:02d}.jpg'), quality=90)

    if callable(cap): cap = cap()
    caption = make_caption(cap, tags, any(u[1] for u in used), footer=(fmt != 'main'))
    with open(os.path.join(outdir, 'caption.txt'), 'w', encoding='utf-8') as f:
        f.write(caption)
    log('format:', fmt, '| lead:', lead['name'], '| focus:', focus['name'])
    return n, caption


def make_caption(lines, tags, has_ai, footer=True):
    lines = list(lines)
    if footer: lines += ['', '연말 모임은 아일랜드이너프 파티룸에서 🥂', '예약은 프로필 링크 → islandenoughpartyroom.com']
    if has_ai:
        lines += ['', '※ 일부 사진은 실제 매장 사진을 바탕으로 만든 AI 연출 이미지입니다.']
    tags = list(dict.fromkeys(COMMON_TAGS + tags))[:25]
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
    ap.add_argument('--format', help='요일 계획 대신 이 형식으로 (예: main = 대표 캐러셀)')
    ap.add_argument('--which', type=int, help='대표 캐러셀 사진 묶음 번호 (0 = 광고용)')
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(KST).date()
    ds = date.isoformat() + (f'-{a.format}' if a.format else ''); outdir = os.path.join(ROOT, 'cards', ds)
    done = os.path.join(outdir, 'posted.json')
    if os.path.exists(done) and not a.force:
        log('이미 게시됨:', json.load(open(done)).get('permalink')); return
    n, caption = make_cards(date, outdir, a.format, a.which)
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

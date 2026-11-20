"""대표 캐러셀 (광고 겸 매주 월요일 게시).

흐름: 가고 싶다(감정) → 공간 → 지점 고르기 → 합리적이다(가격) → 예약하자.
전 지점 공통. 사진은 홈페이지의 실제 고객 파티 사진만 쓴다 (AI 사진 쓰지 않음).
"""
import datetime as dt

from daily_post import (BRANCHES, W, H, GREEN, MINT, CREAM, GOLD, Image, ImageDraw,
                        font, header, crop, shade, fetch_photo)
import content
from content import INK, SUB, LINE, table_price, extra_fee, cfg_branch, target_month

# 장면별 실제 사진 (주마다 돌아가며 사용. 첫 번째가 광고용)
HOOK = ['yeoksam/p03-a26173.jpg', 'suyu/p05-c7df04.jpg', 'yangjae/p04-181516.jpg', 'dosan/p06-94351a.jpg']
DESIRE = ['gangnam/p15-5420ed.jpg', 'gangnam/p04-aada24.jpg', 'yeoksam/p07-9ae8ec.jpg', 'gangnam/p05-6d4b8a.jpg']
VALUE = ['yangjae/p01-ed6a27.jpg', 'yeoksam/p09-694900.jpg', 'suyu/p02-0c0fb2.jpg', 'dosan/p05-9a0f74.jpg']

SHORT = {  # 지점 고르기 카드용 짧은 위치
    'yangjae': '양재역 1번 출구 3분',
    'yeoksam': '선릉역 5번 출구 5분',
    'gangnam': '역삼역 4번 출구 300m',
    'dosan': '압구정로데오역 5분',
    'suyu': '수유역 8번 출구 5분',
}
ORDER = ['gangnam', 'yeoksam', 'yangjae', 'dosan', 'suyu']
PEOPLE = 20


def fit(d, text, weight, size, width):
    """여러 줄 글이 width 안에 들어가도록 글자 크기를 줄인다."""
    while size > 40:
        f = font(weight, size)
        if all(d.textlength(ln, font=f) <= width for ln in text.split('\n')): return f
        size -= 4
    return font(weight, size)


def photo(path):
    return fetch_photo(path)


def story(i, n, path, kicker, title, sub):
    """사진을 크게, 아래에 한 문장."""
    im = shade(shade(crop(photo(path), W, H), 560, H, 245), 0, 170, 160, reverse=True)
    d = ImageDraw.Draw(im); header(d, i, n)
    d.text((60, 820), kicker, font=font('Bold', 32), fill=GOLD)
    d.text((60, 875), title, font=fit(d, title, 'ExtraBold', 84, W - 120), fill='white', spacing=14)
    d.text((60, 1185), sub, font=font('Medium', 38), fill=MINT)
    return im


def cover(i, n, path, ev):
    im = shade(shade(crop(photo(path), W, H), 470, H, 250), 0, 170, 160, reverse=True)
    d = ImageDraw.Draw(im); header(d, i, n)
    badge = f'{dt.date.today().year} 연말 모임'
    bw = int(d.textlength(badge, font=font('Bold', 32))) + 60
    d.rounded_rectangle([60, 740, 60 + bw, 800], radius=30, fill=GOLD)
    d.text((60 + bw // 2, 770), badge, font=font('Bold', 32), fill=GREEN, anchor='mm')
    t = f'{ev}, 1차 끝나고\n또 어디 가요?'
    d.text((60, 830), t, font=fit(d, t, 'ExtraBold', 104, W - 120), fill='white', spacing=14)
    d.text((60, 1100), '올해는 한 공간에서 우리끼리 끝까지.', font=font('Bold', 44), fill=MINT)
    d.text((60, 1240), '아일랜드이너프 · 서울 5곳 단독 대관 파티룸', font=font('Medium', 32), fill=(220, 230, 225))
    return im


def value(i, n, path):
    im = Image.new('RGBA', (W, H), CREAM)
    im.paste(crop(photo(path), W, 760), (0, 0))
    im = shade(im, 0, 170, 160, reverse=True)
    d = ImageDraw.Draw(im); header(d, i, n)
    d.text((60, 820), 'VALUE · 단독 대관', font=font('Bold', 32), fill=(46, 140, 100))
    t = '테이블 하나가 아니라,\n공간 하나를 우리끼리.'
    d.text((60, 875), t, font=fit(d, t, 'ExtraBold', 80, W - 120), fill=GREEN, spacing=14)
    d.text((60, 1100), '예약한 시간 동안 다른 손님 없이 우리 일행만.', font=font('Medium', 38), fill=INK)
    d.text((60, 1160), '자리 옮길 필요 없이 한곳에서 끝까지.', font=font('Medium', 38), fill=INK)
    return im


def branches(i, n, cfg):
    im = Image.new('RGBA', (W, H), CREAM); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=GREEN); header(d, i, n)
    d.text((60, 215), 'CHOICE · 서울 5곳', font=font('Bold', 32), fill=(46, 140, 100))
    d.text((60, 265), '회사 근처, 집 근처.\n가까운 섬을 고르세요.', font=font('ExtraBold', 66), fill=GREEN, spacing=10)
    y = 455
    for bid in ORDER:
        b = next(x for x in BRANCHES if x['id'] == bid); cb = cfg_branch(cfg, bid)
        thumb = crop(fetch_photo(f'{bid}/' + content_space(bid)), 230, 150)
        im.paste(thumb, (60, y))
        d.text((320, y + 12), b['name'], font=font('ExtraBold', 46), fill=GREEN)
        d.text((320, y + 82), SHORT[bid], font=font('Medium', 32), fill=SUB)
        d.text((W - 60, y + 30), f"최대 {cb['max']}명", font=font('Bold', 40), fill=INK, anchor='ra')
        y += 172
        if bid != ORDER[-1]: d.line([(60, y - 11), (W - 60, y - 11)], fill=LINE, width=2)
    return im


_SPACE = {}


def content_space(bid):
    return _SPACE[bid]


def price(i, n, cfg, m):
    rows = []
    for bid in ORDER:
        b = next(x for x in BRANCHES if x['id'] == bid)
        total = table_price(cfg, bid, m, 'night', 0) + max(0, PEOPLE - cfg['baseHeadcount']) * extra_fee(cfg, bid)
        rows.append((b['name'], total, -(-total // PEOPLE // 100) * 100))
    lo, hi = min(r[2] for r in rows), max(r[2] for r in rows)
    head = '1인 장소비 1만 원대' if 10000 <= lo and hi < 20000 else f'1인 장소비 {lo:,}원부터'
    im = Image.new('RGBA', (W, H), CREAM); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=GREEN); header(d, i, n)
    d.text((60, 215), f'PRICE · {m}월 월~목·일요일 밤 5시간', font=font('Bold', 32), fill=(46, 140, 100))
    d.text((60, 265), f'{PEOPLE}명이 모이면,\n{head}.', font=font('ExtraBold', 70), fill=GREEN, spacing=10)
    y = 480
    d.text((60, y), '지점', font=font('Bold', 32), fill=SUB)
    d.text((640, y), f'{PEOPLE}명 대관료', font=font('Bold', 32), fill=SUB, anchor='ra')
    d.text((W - 60, y), '1인', font=font('Bold', 32), fill=SUB, anchor='ra'); y += 64
    for name, total, pp in rows:
        d.text((60, y), name, font=font('Bold', 44), fill=INK)
        d.text((640, y + 6), f'{total:,}원', font=font('Medium', 38), fill=INK, anchor='ra')
        d.text((W - 60, y), f'{pp:,}원', font=font('ExtraBold', 46), fill=GREEN, anchor='ra')
        y += 92
        d.line([(60, y - 18), (W - 60, y - 18)], fill=LINE, width=2)
    notes = [f'장소 대관료 기준 (나이트 19~24시) · 음식·주류는 직접 준비',
             f"보증금 {cfg['deposit']:,}원 별도 (이용 후 반환)",
             '공휴일 전날 · 금·토요일 등 날짜에 따라 요금이 달라요']
    y = 1110
    for t in notes:
        d.text((60, y), '· ' + t, font=font('Medium', 29), fill=SUB); y += 46
    return im, rows, head


def cta(i, n):
    im = Image.new('RGBA', (W, H), GREEN); d = ImageDraw.Draw(im); header(d, i, n)
    d.text((60, 250), '올해 연말 모임,\n여기서 만나요.', font=font('ExtraBold', 92), fill='white', spacing=14)
    d.text((60, 520), '날짜만 정해졌다면, 3단계면 끝.', font=font('Bold', 42), fill=MINT)
    y = 640
    for k, (t, s) in enumerate([('지점 선택', '가까운 곳, 인원에 맞는 곳'), ('날짜 · 요금 확인', '남은 날짜와 그날 요금이 바로 보여요'),
                                ('예약 신청', '승인 후 결제하면 확정')], start=1):
        d.ellipse([60, y, 130, y + 70], fill=GOLD)
        d.text((95, y + 35), str(k), font=font('ExtraBold', 40), fill=GREEN, anchor='mm')
        d.text((160, y), t, font=font('Bold', 44), fill='white')
        d.text((160, y + 58), s, font=font('Medium', 30), fill=(170, 200, 185))
        y += 140
    d.rounded_rectangle([60, 1080, W - 60, 1190], radius=55, fill=GOLD)
    d.text((W // 2, 1135), '날짜 확인하고 예약하기', font=font('ExtraBold', 46), fill=GREEN, anchor='mm')
    d.text((W // 2, 1250), 'islandenoughpartyroom.com', font=font('Bold', 40), fill='white', anchor='mm')
    return im


def build(ctx, which=0):
    """which: 사진 묶음 번호 (0 = 광고용)."""
    cfg, date = ctx['cfg'], ctx['date']
    for bid in ORDER:
        _SPACE[bid] = ctx['photo_index'][bid]['space'][0][0].split('/', 1)[1]
    ev = content.event_word(date); m = target_month(date)
    pick = lambda L: L[which % len(L)]
    price_box = {}

    def p(i, n):
        im, rows, head = price(i, n, cfg, m); price_box.update(rows=rows, head=head); return im

    slides = [
        lambda i, n: cover(i, n, pick(HOOK), ev),
        lambda i, n: story(i, n, pick(DESIRE), 'DESIRE · 우리만의 밤', '먹고, 웃고, 게임하고.\n분위기 좋으면 노래까지.',
                           '회사 사람들과도, 오랜 친구들과도.'),
        lambda i, n: value(i, n, pick(VALUE)),
        lambda i, n: branches(i, n, cfg),
        p,
        lambda i, n: cta(i, n),
    ]
    maxp = max(cfg_branch(cfg, b)['max'] for b in ORDER)

    def caption():
        lo = min(r[2] for r in price_box['rows'])
        lines = [f'올해 {ev}, 1차 끝나고 또 어디 갈지 고민하지 마세요. 🥂', '',
                 '우리끼리 한 공간에서', '먹고, 웃고, 게임하고, 노래까지.', '',
                 '📍 아일랜드이너프 서울 5곳',
                 '강남(역삼역) · 역삼(선릉역) · 양재 · 도산공원 · 수유', '',
                 f'✔ 공간 전체를 우리 일행만 단독 대관 (최대 {maxp}명)',
                 '✔ 음식 · 주류 · 배달 자유롭게 반입',
                 '✔ 빔프로젝터 · 무선 마이크 무료',
                 f"✔ {PEOPLE}명이 모이면 {price_box['head']} ({m}월 월~목·일요일 밤 5시간)", '',
                 '올해 연말 모임, 날짜만 정하면 됩니다.',
                 '👇 지점별 남은 날짜와 요금은 홈페이지에서 바로 확인하세요.',
                 'islandenoughpartyroom.com (프로필 링크)', '',
                 f"*장소 대관료 기준이며 음식·주류는 별도입니다. 보증금 {cfg['deposit']:,}원은 이용 후 반환되며, "
                 '금·토요일과 공휴일 전날 등은 요금이 달라요.']
        return lines
    return slides, caption, ['송년회장소', '연말모임장소', '회식장소', '단체모임장소', '서울파티룸',
                             '강남파티룸', '역삼파티룸', '선릉파티룸', '양재파티룸', '도산공원파티룸', '수유파티룸']

"""요일별 콘텐츠 (총무의 고민을 해결하는 카드뉴스).

월 1인 가격 · 화 송년회 게임 · 수 남은 날짜(실시간) · 목 이거 돼요? · 금 밸런스 게임
토 실제 파티 사진(지점 집중 / 사진 모음 번갈아) · 일 총무 가이드 / D-day 번갈아

숫자는 전부 홈페이지 설정(/api/config)과 예약 현황(/api/availability)에서 가져온다.
"""
import datetime as dt
import math

from daily_post import (BRANCHES, W, H, GREEN, MINT, CREAM, GOLD, SITE, Image, ImageDraw,
                        font, header, get_json, card_cover, card_photo, card_cta, card_branch, load, crop, ai_badge)

INK = (32, 42, 37); SUB = (110, 120, 115); LINE = (222, 216, 204); RED = (196, 72, 52)
WEEKDAY_KO = '월화수목금토일'


# ---------- 요금 (홈페이지 pricing.js 와 같은 규칙) ----------
def _on(lst, date):
    return any(x['date'] == date.isoformat() for x in lst)


def day_type(cfg, date, slot):
    """0: 월~목, 1: 금, 2: 토, 3: 일"""
    if _on(cfg.get('specialDays', []), date): return 2
    base = [0, 0, 0, 0, 1, 2, 3][date.weekday()]
    if slot == 'day': return 2 if _on(cfg['holidays'], date) else base
    if base in (1, 2): return base
    if _on(cfg['holidays'], date + dt.timedelta(1)): return 1
    if _on(cfg['holidays'], date): return 0
    return base


def season(cfg, month):
    return 'peak' if month in cfg.get('peakMonths', []) else 'normal'


def regular_price(cfg, bid, date, slot):
    b = next(x for x in cfg['branches'] if x['id'] == bid)
    return b['prices'][season(cfg, date.month)][slot][day_type(cfg, date, slot)]


def slot_price(cfg, bid, date, slot):
    for o in cfg.get('overrides', []):
        if o['date'] == date.isoformat() and o['slot'] == slot and o['branch'] in (bid, '*'):
            return o['price']
    return regular_price(cfg, bid, date, slot)


def extra_fee(cfg, bid):
    b = next(x for x in cfg['branches'] if x['id'] == bid)
    return b.get('extraPerPerson') if isinstance(b.get('extraPerPerson'), int) else cfg['extraPerPerson']


def table_price(cfg, bid, month, slot, kind):
    """요금표 금액. kind 0: 월~목, 1: 금, 2: 토, 3: 일"""
    b = next(x for x in cfg['branches'] if x['id'] == bid)
    return b['prices'][season(cfg, month)][slot][kind]


def per_person(cfg, bid, month, people):
    total = table_price(cfg, bid, month, 'night', 0) + max(0, people - cfg['baseHeadcount']) * extra_fee(cfg, bid)
    return total, int(math.ceil(total / people / 100) * 100)


def won(v):
    return f'{v:,}원'


def man(v):
    return f'{v / 10000:g}만원'


def target_month(date):
    """홍보할 달: 11월에는 12월 모임을 미리 잡게 한다."""
    return 12 if date.month in (11, 12) and not (date.month == 12 and date.day >= 26) else (date.month % 12) + 1


def event_word(date):
    if date.month == 12 and 21 <= date.day <= 25: return '크리스마스 파티'
    if (date.month == 12 and date.day >= 26) or date.month == 1: return '신년회'
    return '송년회'


def cfg_branch(cfg, bid):
    return next(x for x in cfg['branches'] if x['id'] == bid)


# ---------- 공통 카드 ----------
def base_card(i, n, kicker, title, bg=CREAM, dark=False, photo=None, top=900):
    im = Image.new('RGBA', (W, H), GREEN if dark else bg)
    if photo is not None:
        fn, is_ai = load(photo)
        im.paste(crop(fn, W, H - top), (0, top))
    d = ImageDraw.Draw(im)
    if photo is not None and is_ai: ai_badge(d, W - 40, H - 40)
    if not dark: d.rectangle([0, 0, W, 170], fill=GREEN)
    header(d, i, n)
    d.text((60, 220), kicker, font=font('Bold', 34), fill=GOLD if dark else (46, 140, 100))
    d.text((60, 280), title, font=font('ExtraBold', 70), fill='white' if dark else GREEN, spacing=12)
    return im, d


def wrap(d, text, f, width):
    out = []
    for para in text.split('\n'):
        line = ''
        for word in para.split(' '):
            t = (line + ' ' + word).strip()
            if d.textlength(t, font=f) <= width: line = t
            else: out.append(line); line = word
        out.append(line)
    return out


def bullet_list(d, items, y, color=INK, sub_color=SUB, dot=(46, 140, 100), size=40):
    for head, desc in items:
        d.ellipse([62, y + 16, 82, y + 36], fill=dot)
        d.text((104, y), head, font=font('Bold', size), fill=color)
        y += size + 22
        if desc:
            for ln in wrap(d, desc, font('Medium', 32), W - 164):
                d.text((104, y), ln, font=font('Medium', 32), fill=sub_color); y += 46
        y += 30
    return y


def note(d, text, dark=False):
    d.text((60, H - 70), text, font=font('Medium', 26), fill=(170, 200, 185) if dark else (140, 140, 135))


# ---------- 월: 1인 가격 ----------
def fmt_price(ctx):
    cfg, date, b, take = ctx['cfg'], ctx['date'], ctx['focus'], ctx['take']
    m = target_month(date); cb = cfg_branch(cfg, b['id']); mx = cb['max']; ev = event_word(date)
    sizes = [p for p in (10, 20, 30, 40, 50, 60) if p <= mx]
    if mx not in sizes: sizes.append(mx)
    head = 30 if mx >= 30 else mx
    _, pp = per_person(cfg, b['id'], m, head)
    base = table_price(cfg, b['id'], m, 'night', 0)
    sat = table_price(cfg, b['id'], m, 'night', 2)
    slides = [lambda i, n: card_cover(take(b, 0), i, n, '1인 가격 공개', f'{head}명 {ev},\n1인 {pp:,}원',
                                      f"{b['name']} · {m}월 월~목·일 나이트 기준")]

    def table(i, n):
        im, d = base_card(i, n, f"{b['name']} · {m}월 월~목·일 나이트 5시간", '인원별 1인 금액')
        y = 470
        d.text((60, y), '인원', font=font('Bold', 34), fill=SUB); d.text((520, y), '총 대관료', font=font('Bold', 34), fill=SUB, anchor='ra')
        d.text((W - 60, y), '1인', font=font('Bold', 34), fill=SUB, anchor='ra'); y += 70
        for p in sizes[-6:]:
            t, v = per_person(cfg, b['id'], m, p)
            hi = p == head
            if hi: d.rounded_rectangle([40, y - 18, W - 40, y + 70], radius=20, fill=(232, 244, 236))
            d.text((60, y), f'{p}명', font=font('ExtraBold' if hi else 'Bold', 46), fill=GREEN if hi else INK)
            d.text((520, y + 6), won(t), font=font('Medium', 38), fill=INK, anchor='ra')
            d.text((W - 60, y), won(v), font=font('ExtraBold', 46), fill=GREEN if hi else INK, anchor='ra')
            y += 100
        note(d, f"※ 홈페이지 요금 기준 · {cfg['baseHeadcount']}인 초과 1인 {extra_fee(cfg, b['id']):,}원 · 보증금 {cfg['deposit']:,}원 별도(반환)")
        return im

    def inside(i, n):
        im, d = base_card(i, n, '이 금액에 포함된 것', '5시간 동안\n전부 우리 거')
        bullet_list(d, [('공간 전체 단독 대관', f"최대 {mx}명 · 다른 손님 없이 우리 일행만"),
                        ('빔프로젝터 · 무선 마이크 2개', '유튜브 MR로 노래방까지 추가 요금 없이'),
                        ('음식 · 주류 · 배달 자유 반입', '좋아하는 메뉴로, 원하는 만큼'),
                        ('주말보다 저렴한 평일', f"같은 공간 토요일 나이트 {man(sat)} → 월~목·일 {man(base)}")], 560)
        return im

    slides += [table, inside, lambda i, n: card_photo(take(b, 1), i, n, b['name']), lambda i, n: card_cta(take(b, 2), i, n)]
    cap = [f'💰 {head}명이 모이면 1인 {pp:,}원.',
           f"{b['name']} {m}월 월~목·일요일 나이트(19~24시) 요금을 인원별로 계산해 봤어요 👉", '',
           f"✔ 5시간 동안 공간 전체 단독 이용 (최대 {mx}명)", '✔ 빔프로젝터 · 무선 마이크 · 보드게임 무료',
           '✔ 음식 · 주류 · 배달 자유 반입 (음식비는 별도)', '',
           '총무님, 이 카드 그대로 단톡방에 공유하세요 😉']
    return slides, cap, ['송년회장소', '회식장소', '단체모임장소'] + b['tags']


# ---------- 화: 게임 ----------
GAMES = [
    ('빔프로젝터 스피드 퀴즈', '팀을 나눠 큰 화면에 문제를 띄우세요. 유튜브 퀴즈 영상만 틀어도 바로 시작.', '전 지점 (수유점은 86인치 TV)'),
    ('유튜브 MR 노래 배틀', '무선 마이크 2개로 팀 대항전. 점수 앱 하나면 노래방 부럽지 않아요.', '전 지점 · 마이크 무료'),
    ('다트 토너먼트', '대진표를 빔에 띄우고 1:1 토너먼트. 꼴찌는 다음 회식 총무!', '양재점'),
    ('미니 당구 내기', '두 명씩 짝지어 한 판 승부. 구경하는 사람이 더 신나요.', '양재점 · 역삼점'),
    ('보드게임 + 마니또 공개', '한 해 동안 몰래 챙겨 준 마니또를 공개하며 마무리.', '보드게임: 양재 · 역삼 · 도산 · 수유'),
]


def fmt_games(ctx):
    cfg, date, take = ctx['cfg'], ctx['date'], ctx['take']
    ev = event_word(date); cover_b = ctx['lead']
    slides = [lambda i, n: card_cover(take(cover_b, 0), i, n, '저장 필수', f'{ev} 안 망하는\n게임 5',
                                      '아일랜드이너프 무료 시설로 전부 가능')]
    for k, (t, how, where) in enumerate(GAMES, start=1):
        def g(i, n, k=k, t=t, how=how, where=where):
            im, d = base_card(i, n, f'GAME {k}', t, photo=ctx['strip'](k))
            y = 470
            for ln in wrap(d, how, font('Medium', 42), W - 120):
                d.text((60, y), ln, font=font('Medium', 42), fill=INK); y += 64
            d.rounded_rectangle([60, y + 50, W - 60, y + 150], radius=26, fill=(232, 244, 236))
            d.text((100, y + 100), '📍 가능 지점'.replace('📍 ', ''), font=font('Bold', 32), fill=(46, 140, 100), anchor='lm')
            d.text((W - 100, y + 100), where, font=font('Bold', 34), fill=GREEN, anchor='rm')
            d.text((W - 60, 250), f'{k}/5', font=font('ExtraBold', 90), fill=(232, 228, 218), anchor='ra')
            return im
        slides.append(g)
    slides.append(lambda i, n: card_cta(take(cover_b, 1), i, n))
    cap = [f'🎮 {ev} 분위기, 게임 하나로 갈립니다.', '총무님 이거 저장해 두세요 📌 장비는 저희가 다 준비해 뒀어요 👉', '']
    cap += [f'{k}. {t} — {w}' for k, (t, _, w) in enumerate(GAMES, start=1)]
    cap += ['', '빔프로젝터 · 무선 마이크 · 보드게임은 모두 추가 요금 없이 이용하실 수 있어요.']
    return slides, cap, ['송년회게임', '회식게임', '단체게임', '송년회장소']


# ---------- 수: 남은 날짜 (실시간) ----------
def open_weekends(cfg, date, m):
    """지점별로 남은 금·토 나이트 날짜 (오늘 이후, 홍보 달 안)."""
    year = date.year if m >= date.month else date.year + 1
    out = {}
    for b in BRANCHES:
        av = get_json(f"{SITE}/api/availability?branch={b['id']}")
        taken = set(av.get('taken', []))
        d0 = max(date + dt.timedelta(1), dt.date(year, m, 1))
        days = []
        d = d0
        while d.month == m:
            if d.weekday() in (4, 5) and f'{d.isoformat()}|night' not in taken: days.append(d)
            d += dt.timedelta(1)
        out[b['id']] = (days, taken)
    return out


def deals(cfg, date, avail):
    """앞으로 10일 안의 할인 날짜 (관리자가 요금표보다 낮게 바꿔 둔 비어 있는 타임)."""
    res = []
    for b in BRANCHES:
        taken = avail[b['id']][1]
        for k in range(1, 11):
            d = date + dt.timedelta(k)
            for slot in ('day', 'night'):
                if f'{d.isoformat()}|{slot}' in taken: continue
                reg, now = regular_price(cfg, b['id'], d, slot), slot_price(cfg, b['id'], d, slot)
                if now < reg: res.append((d, b, slot, now, reg))
    return sorted(res, key=lambda x: (x[0], -(x[4] - x[3])))


def md(d):
    return f'{d.month}/{d.day}({"월화수목금토일"[d.weekday()]})'


def fmt_avail(ctx):
    cfg, date, take = ctx['cfg'], ctx['date'], ctx['take']
    m = target_month(date); av = open_weekends(cfg, date, m); dl = deals(cfg, date, av)
    total = sum(len(v[0]) for v in av.values()); lead = ctx['lead']
    slides = [lambda i, n: card_cover(take(lead, 0), i, n, '실시간 예약 현황', f'{m}월 금·토 밤,\n남은 날짜 {total}개',
                                      f'{date.month}월 {date.day}일 기준 · 5개 지점 합계')]

    def board(i, n):
        im, d = base_card(i, n, f'{m}월 금·토 나이트 (19~24시)', '지점별 남은 날짜')
        y = 470
        for b in BRANCHES:
            days = av[b['id']][0]
            d.text((60, y), b['name'], font=font('ExtraBold', 42), fill=GREEN)
            d.text((W - 60, y + 4), f'{len(days)}개 남음' if days else '마감', font=font('Bold', 34),
                   fill=RED if len(days) <= 2 else (46, 140, 100), anchor='ra')
            y += 64
            txt = '  '.join(md(x) for x in days[:6]) + (' …' if len(days) > 6 else '') if days else '금·토 나이트 모두 예약 완료'
            d.text((60, y), txt, font=font('Medium', 30), fill=SUB if days else RED); y += 74
            d.line([(60, y - 22), (W - 60, y - 22)], fill=LINE, width=2)
        note(d, f'※ {date.month}월 {date.day}일 홈페이지 예약 현황 기준 · 실시간으로 바뀔 수 있어요')
        return im

    slides.append(board)
    if dl:
        def deal(i, n):
            im, d = base_card(i, n, '앞으로 10일 · 비어 있는 시간 특가', '이번 주\n할인 날짜', dark=True)
            y = 560
            for x, b, slot, now, reg in dl[:6]:
                d.text((60, y), f"{md(x)} {b['name']} {'나이트' if slot == 'night' else '데이'}", font=font('Bold', 38), fill='white')
                d.text((W - 60, y - 4), man(now), font=font('ExtraBold', 46), fill=GOLD, anchor='ra')
                d.text((W - 60, y + 50), f'요금표 {man(reg)}', font=font('Medium', 26), fill=(170, 200, 185), anchor='ra')
                y += 110
            note(d, '※ 홈페이지 예약 화면 요금 기준 · 먼저 예약하시는 분께', dark=True)
            return im
        slides.append(deal)

    def alt(i, n):
        b = BRANCHES[1]
        sat, wk = table_price(cfg, b['id'], m, 'night', 2), table_price(cfg, b['id'], m, 'night', 0)
        im, d = base_card(i, n, '금·토가 꽉 찼다면?', '일요일 밤 ·\n평일 밤이 정답')
        bullet_list(d, [(f"{b['name']} {m}월 토요일 나이트", man(sat)),
                        (f"같은 공간 월~목 · 일요일 나이트", f'{man(wk)} ({round((1 - wk / sat) * 100)}% 저렴)'),
                        ('다음 날 출근 걱정된다면', '데이타임(10~17시) 송년회도 인기예요')], 560)
        return im

    slides += [alt, lambda i, n: card_cta(take(lead, 1), i, n)]
    cap = [f'🔥 {m}월 금·토 밤, 5개 지점 합쳐 {total}개 남았어요. ({date.month}/{date.day} 기준)', '']
    for b in BRANCHES:
        days = av[b['id']][0]
        cap.append(f"📍 {b['name']}: " + (', '.join(md(x) for x in days) if days else '금·토 나이트 마감'))
    if dl:
        cap += ['', '💸 앞으로 10일 할인 날짜'] + [f"· {md(x)} {b['name']} {'나이트' if s == 'night' else '데이'} {man(now)} (요금표 {man(reg)})"
                                             for x, b, s, now, reg in dl[:6]]
    cap += ['', '금·토가 없다면 월~목 · 일요일 밤이 훨씬 저렴해요.']
    return slides, cap, ['송년회장소', '송년회예약', '연말모임장소']


# ---------- 목: 이거 돼요? ----------
def fmt_faq(ctx):
    cfg, take, lead = ctx['cfg'], ctx['take'], ctx['lead']
    qa = [
        [('술 가져가도 돼요?', '돼요. 음식 · 주류 모두 자유롭게 반입하세요.'),
         ('배달 시켜도 돼요?', '돼요. 데울 땐 전자레인지를 쓰시면 돼요. (가스버너 등 화기는 안 돼요)')],
        [('노래 불러도 돼요?', '돼요. 유튜브 MR + 무선 마이크 2개, 추가 요금 없어요.'),
         ('케이크 초 켜도 돼요?', '돼요. 폭죽 · 꽃가루(컨페티)만 안 돼요.')],
        [('풍선 · 현수막 달아도 돼요?', '돼요. 벽 손상 없게 끈으로만 달아 주세요.'),
         ('직원 눈치 보이지 않아요?', '무인 입실이라 처음부터 끝까지 우리끼리예요.')],
        [('몇 시까지 놀 수 있어요?', '나이트 19~24시, 데이 10~17시, 둘 다 하면 올데이 10~24시.'),
         ('뒷정리 귀찮은데요?', f"청소대행 1인 {cfg['cleaningPerPerson']:,}원(최대 {man(cfg['cleaningMax'])}) 신청하면 그냥 나가셔도 돼요.")],
    ]
    slides = [lambda i, n: card_cover(take(lead, 0), i, n, '처음이라면 필독', '파티룸에서\n이거 돼요?', '자주 묻는 질문 8가지, 한 번에 정리')]
    for k, pair in enumerate(qa):
        def c(i, n, pair=pair, k=k):
            im, d = base_card(i, n, f'Q&A {k * 2 + 1} · {k * 2 + 2}', '', photo=ctx['strip'](k), top=980)
            y = 300
            for q, a in pair:
                d.text((60, y), 'Q.', font=font('ExtraBold', 60), fill=GOLD)
                d.text((150, y + 4), q, font=font('ExtraBold', 52), fill=GREEN); y += 110
                d.text((60, y), 'A.', font=font('ExtraBold', 60), fill=(46, 140, 100))
                for ln in wrap(d, a, font('Medium', 40), W - 220):
                    d.text((150, y + 8), ln, font=font('Medium', 40), fill=INK); y += 60
                y += 110
            return im
        slides.append(c)
    slides.append(lambda i, n: card_cta(take(lead, 1), i, n))
    cap = ['❓ "술 가져가도 돼요?" "노래 불러도 돼요?"', '파티룸 처음이신 분들이 제일 많이 물어보시는 8가지, 답은 거의 다 "돼요" 입니다 👉', '']
    cap += [f'Q. {q}\nA. {a}' for pair in qa for q, a in pair]
    return slides, cap, ['파티룸', '파티룸추천', '송년회장소']


# ---------- 금: 밸런스 게임 ----------
def fmt_vs(ctx):
    cfg, date, take, lead = ctx['cfg'], ctx['date'], ctx['take'], ctx['lead']
    m = target_month(date); ev = event_word(date)
    _, pp = per_person(cfg, 'yeoksam', m, 20)
    slides = [lambda i, n: card_cover(take(lead, 0), i, n, '당신의 선택은?', f'{ev},\nA vs B', '댓글로 A 또는 B 남겨 주세요')]

    def side(i, n, tag, title, items, dark, ph):
        im, d = base_card(i, n, tag, title, dark=dark, photo=ph, top=920)
        bullet_list(d, items, 480, color='white' if dark else INK, sub_color=(170, 200, 185) if dark else SUB,
                    dot=GOLD if dark else (46, 140, 100))
        return im

    slides.append(lambda i, n: side(i, n, 'A', '1차 고깃집 →\n2차 호프 → 3차 노래방',
                                    [('이동 2번', '코트 챙기고, 택시 잡고, 자리 또 찾고'), ('결제 3번', '정산하다 술이 깹니다'),
                                     ('옆 테이블 신경', '건배사도 작게, 노래는 따로')], False, ctx['strip'](4)))
    slides.append(lambda i, n: side(i, n, 'B', '파티룸 한 곳에서\n5시간 통째로',
                                    [('이동 0번', '먹고 마시고 노래까지 한 공간'), ('결제 1번', f'20명이면 대관료 1인 {pp:,}원 (역삼점 평일 밤)'),
                                     ('우리만의 공간', '건배사 크게, 노래는 마이크로')], True, take(lead, 3)))
    slides.append(lambda i, n: card_photo(take(lead, 1), i, n, lead['name']))
    slides.append(lambda i, n: card_cta(take(lead, 2), i, n))
    cap = [f'⚖️ {ev}, 당신의 선택은?', '', 'A) 1차 고깃집 → 2차 호프 → 3차 노래방', 'B) 파티룸 한 곳에서 5시간 통째로', '',
           '👇 댓글에 A 또는 B 남겨 주세요!', f'(B를 고른 총무님께: 역삼점 {m}월 평일 밤 20명이면 대관료 1인 {pp:,}원이에요)']
    return slides, cap, ['밸런스게임', '회식', '송년회', '회식장소']


# ---------- 일: 총무 가이드 ----------
def fmt_guide(ctx):
    cfg, date, take, lead = ctx['cfg'], ctx['date'], ctx['take'], ctx['lead']
    ev = event_word(date)
    steps = [
        ('D-14', '장소 확정', '인원 범위를 먼저 정하고 대관. 12월 금·토 밤은 가장 먼저 마감돼요.'),
        ('D-7', '메뉴 · 술 정하기', '배달 메뉴는 도착 시간을 입실 30분 뒤로. 일회용 접시 · 컵도 챙기면 설거지 끝.'),
        ('D-3', '프로그램 준비', '빔프로젝터에 올해 사진 슬라이드 + 게임 1~2개면 충분해요.'),
        ('D-day', '이것만 챙기세요', '생수 · 얼음은 꼭 준비 (정수기 · 제빙기 없음). 장식은 끈으로.'),
        ('정산', '1인 금액 공지', f"(대관료 + 음식값) ÷ 인원. 정리가 귀찮으면 청소대행 1인 {cfg['cleaningPerPerson']:,}원."),
    ]
    slides = [lambda i, n: card_cover(take(lead, 0), i, n, f'{ev} 총무 가이드', '총무 맡았다고요?\n이거 저장하세요', '2주 전부터 당일 정산까지 한 번에')]
    for k, (dd, t, how) in enumerate(steps):
        def s(i, n, dd=dd, t=t, how=how, k=k):
            im, d = base_card(i, n, '', '', photo=ctx['strip'](k + 1))
            d.text((60, 260), dd, font=font('ExtraBold', 150), fill=GOLD)
            d.text((60, 470), t, font=font('ExtraBold', 70), fill=GREEN)
            y = 600
            for ln in wrap(d, how, font('Medium', 44), W - 120):
                d.text((60, y), ln, font=font('Medium', 44), fill=INK); y += 68
            return im
        slides.append(s)
    slides.append(lambda i, n: card_cta(take(lead, 1), i, n))
    cap = [f'📋 {ev} 총무 맡으셨나요? 이 게시물 저장해 두세요 📌', '']
    cap += [f'{dd} | {t} — {how}' for dd, t, how in steps]
    cap += ['', '장소는 아일랜드이너프가 해결해 드릴게요.']
    return slides, cap, ['송년회준비', '총무', '송년회장소', '회식준비']


# ---------- 일: D-day ----------
def fmt_dday(ctx):
    cfg, date, take, lead = ctx['cfg'], ctx['date'], ctx['take'], ctx['lead']
    xmas = dt.date(date.year, 12, 25); target, label = (xmas, '크리스마스') if date < xmas else (dt.date(date.year + 1, 1, 1), '새해')
    left = (target - date).days
    weekends = [date + dt.timedelta(k) for k in range(1, left) if (date + dt.timedelta(k)).weekday() == 5]
    m = target_month(date)
    slides = [lambda i, n: card_cover(take(lead, 0), i, n, f'{label} 카운트다운', f'{label}까지\nD-{left}', f'남은 토요일은 {len(weekends)}번')]

    def wk(i, n):
        im, d = base_card(i, n, f'{label} 전 남은 주말', f'토요일 {len(weekends)}번,\n벌써 이것뿐')
        y = 600
        for w in weekends:
            d.text((60, y), f'{w.month}월 {w.day}일 (토)', font=font('Bold', 46), fill=INK); y += 80
        d.text((60, y + 40), '"언제 볼래?" 보내기 전에, 장소부터 잡아 두세요.', font=font('Medium', 36), fill=SUB)
        return im

    def alt(i, n):
        b = BRANCHES[0]
        im, d = base_card(i, n, '주말이 꽉 찼다면', '일요일 밤도\n충분히 연말')
        bullet_list(d, [(f"{b['name']} {m}월 토요일 나이트", man(table_price(cfg, b['id'], m, 'night', 2))),
                        ('같은 공간 일요일 나이트', man(table_price(cfg, b['id'], m, 'night', 3))),
                        ('다음 날 출근이 걱정되면', '데이타임(10~17시) 브런치 파티')], 560)
        return im

    slides += [wk, alt, lambda i, n: card_photo(take(lead, 1), i, n, lead['name']), lambda i, n: card_cta(take(lead, 2), i, n)]
    cap = [f'🗓️ {label}까지 D-{left}. 남은 토요일은 {len(weekends)}번이에요.', '',
           '단톡방에 "언제 볼래?" 보내기 전에, 장소부터 잡아 두세요.', '주말이 꽉 찼다면 일요일 밤 · 평일 밤이 훨씬 저렴해요.']
    return slides, cap, ['크리스마스파티', '연말파티', '크리스마스파티룸', '연말모임']


# ---------- 토: 실제 파티 사진 ----------
def fmt_photos(ctx, gallery):
    cfg, date, take, b = ctx['cfg'], ctx['date'], ctx['take'], ctx['focus']
    ev = event_word(date)
    if gallery:
        lead = ctx['lead']
        slides = [lambda i, n: card_cover(take(lead, 0), i, n, '파티 갤러리', f'이번 주\n{ev} 무드', '아일랜드이너프 5개 지점 모아 보기')]
        for j in range(5):
            bb = BRANCHES[(ctx['day'] + j) % len(BRANCHES)]
            slides.append(lambda i, n, bb=bb, j=j: card_photo(take(bb, 1 + (j == 0)), i, n, bb['name']))
        slides.append(lambda i, n: card_cta(take(lead, 3), i, n))
        cap = [f'📸 이번 주 아일랜드이너프 {ev} 무드 👉', '', *[f"📍 {x['name']} | {x['loc']}" for x in BRANCHES]]
        return slides, cap, ['파티룸', '연말파티', '서울파티룸']
    cb = cfg_branch(cfg, b['id'])
    slides = [lambda i, n: card_cover(take(b, 0), i, n, f"{b['name']} 집중 탐구", f"{b['name']},\n직접 보세요", f"{b['loc']} · 최대 {cb['max']}명")]
    for k in range(1, 5):
        slides.append(lambda i, n, k=k: card_photo(take(b, k), i, n))
    slides.append(lambda i, n: card_branch(take(b, 5), i, n, b, cfg, date))
    slides.append(lambda i, n: card_cta(take(b, 6), i, n))
    cap = [f"📍 오늘은 {b['name']}을 보여 드릴게요 👉", '', f"🚇 {b['loc']}", f"👥 {b['cap']}"] + [f'✔ {f}' for f in b['feats']]
    return slides, cap, b['tags']


# ---------- 요일 배정 ----------
def plan(date):
    """요일 → 형식. 토 · 일은 주마다 번갈아."""
    wk = date.isocalendar()[1]
    return {0: 'price', 1: 'games', 2: 'avail', 3: 'faq', 4: 'vs',
            5: 'gallery' if wk % 2 else 'branch',
            6: 'dday' if (wk % 2 and date.month == 12) else 'guide'}[date.weekday()]


def build(fmt, ctx):
    f = {'price': fmt_price, 'games': fmt_games, 'avail': fmt_avail, 'faq': fmt_faq, 'vs': fmt_vs,
         'guide': fmt_guide, 'dday': fmt_dday}
    if fmt in f: return f[fmt](ctx)
    return fmt_photos(ctx, gallery=(fmt == 'gallery'))

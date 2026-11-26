"""Builds public/tradevault/spot/setups.json (the /spot chart game + ks-live.js on the sales pages) from real
gold futures data, with every overlay computed by a line-by-line port of Jay's KILLSHOT Pine script
(api/Killshot.txt, v.17). Nothing looks ahead: each value is what Killshot showed live when that bar closed.

  python3 tools/spot/build_killshot.py            (reads tools/spot/data/*.json, see fetch.sh)

What is ported (Pine line refs are to api/Killshot.txt):
  EMAs 20 / 50 / 238 + blue/red trend shading (20 > 50)                    118-138
  Trend table: 20 EMA vs 50 EMA on M1 M5 M15 M30 H4 D (developing HTF bar)   156-370
  POC: body/wick-weighted volume in 24 channels (chart: 72 bars on M5;
       table: 24 bars on M15 M30 H1)                                         206-448
  Support & resistance zones (ATR-validated swing highs/lows)               465-594
  Stars: the 3-depth zigzag (5/1/3 yellow, 13/8/5 blue, 34/13/8 red/lime),
       including repaint (the current leg's star moves until the leg ends)   616-707
  Trade clock sessions (UTC, DST/standard)                                   727-740
  Killshot signal = 20/50 EMA cross on bar close, arrows only in trade time,
       with the 5 confirmations: candle match, trade time, 238 behind,
       with the upper-timeframe trend (M5 -> M30), POC                       812-901

Game rule (from Jay; the Pine script itself has no stop/target): the signal is the Killshot arrow (blue buy /
red sell) with all 5 confirmations. Don't chase it: wait for price to come back and test the line (20 EMA) and
enter there. Stop 2 x ATR(14), target 1:1 (1R). Stars are where you protect the trade;
the game labels them but they don't change the 1:1 result.
"""
import bisect, glob, json, math, os, random, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(HERE, '..', '..', 'public', 'tradevault', 'spot', 'setups.json')
ET = ZoneInfo('America/New_York')
TF = 60 if '--m5' not in sys.argv else 300   # chart: gold 1-minute, like Jay's replay (--m5 for 5-minute)
MINTICK = 0.1
RR, WAIT_MAX, STOP_ATR = 1, 60, 2.0   # stop 2 x ATR(14); Jay: Killshot pays 1:1; wait up to an hour of 1m bars for the test of the line
NA = None


# ---------------------------------------------------------------- data
def yahoo(fn):
    r = json.load(open(fn))['chart']['result'][0]; q = r['indicators']['quote'][0]
    out = {}
    for t, o, h, l, c, v in zip(r['timestamp'], q['open'], q['high'], q['low'], q['close'], q['volume']):
        if None in (o, h, l, c):
            continue
        out[t] = [t, o, h, l, c, v or 0]
    return out

M1 = {}
for fn in sorted(glob.glob(os.path.join(DATA, 'gc1m_*.json'))):
    M1.update(yahoo(fn))
M1 = [M1[k] for k in sorted(M1)]
C = [list(x) for x in M1] if TF == 60 else [v for k, v in sorted(yahoo(os.path.join(DATA, 'gc5m.json')).items()) if k % TF == 0]
D1 = [v for k, v in sorted(yahoo(os.path.join(DATA, 'gc1d.json')).items())]
N = len(C)
print(TF // 60, 'm bars', N, datetime.fromtimestamp(C[0][0], timezone.utc), '->', datetime.fromtimestamp(C[-1][0], timezone.utc))


# ---------------------------------------------------------------- Pine built-ins
def ema(src, n):
    """ta.ema: seeded with the SMA of the first n values."""
    out = [NA] * len(src); a = 2 / (n + 1); s = NA
    for i, x in enumerate(src):
        if i < n - 1:
            continue
        s = sum(src[i - n + 1:i + 1]) / n if s is NA else a * x + (1 - a) * s
        out[i] = s
    return out

def rma(src, n):
    out = [NA] * len(src); s = NA
    for i, x in enumerate(src):
        if i < n - 1:
            continue
        s = sum(src[i - n + 1:i + 1]) / n if s is NA else (x + (n - 1) * s) / n
        out[i] = s
    return out

def atr_of(c, n=14):
    tr = [c[0][2] - c[0][3]] + [max(c[i][2] - c[i][3], abs(c[i][2] - c[i - 1][4]), abs(c[i][3] - c[i - 1][4])) for i in range(1, len(c))]
    return rma(tr, n)

# Yahoo has the odd bad print (one wick 10x normal); TradingView's feed doesn't, so trim it.
A0 = atr_of(C)
for i in range(15, N):
    t, o, h, l, c, v = C[i]; lim = 5 * A0[i - 1]; top, bot = max(o, c), min(o, c)
    if h - top > lim: C[i][2] = top + A0[i - 1] * 0.5
    if bot - l > lim: C[i][3] = bot - A0[i - 1] * 0.5

O = [x[1] for x in C]; Hh = [x[2] for x in C]; L = [x[3] for x in C]; CL = [x[4] for x in C]; V = [x[5] for x in C]
E20, E50, E238 = ema(CL, 20), ema(CL, 50), ema(CL, 238)
ATR = atr_of(C)


# ---------------------------------------------------------------- trade clock (727-728)
def session(t):
    d = datetime.fromtimestamp(t, timezone.utc)
    mo = datetime.fromtimestamp(t, ET).month
    m = d.hour * 60 + d.minute
    if 3 <= mo < 11:   # DST: '0530-0900,1100-1300,1345-1930:23456' (Mon-Fri)
        if d.weekday() > 4: return False
        rng = ((330, 540), (660, 780), (825, 1170))
    else:              # standard: '0630-1000,1200-1400,1445-2030:1234567'
        rng = ((390, 600), (720, 840), (885, 1230))
    return any(a <= m < b for a, b in rng)
SESS = [session(x[0]) for x in C]


# ---------------------------------------------------------------- higher timeframes (developing bar, as live)
def et_local(t):
    return t + int(datetime.fromtimestamp(t, ET).utcoffset().total_seconds())

def bucket(t, sec):
    if sec == 14400:   # CME 4h bars start at the 18:00 ET session open
        return (et_local(t) - 18 * 3600) // sec
    if sec == 86400:   # trading day: 18:00 ET to 17:00 ET
        return (et_local(t) + 6 * 3600) // 86400
    return t // sec

def htf_bars(sec):
    """Completed + developing HTF bars, and for each chart bar: (htf index, developing o,h,l,c,v)."""
    keys, bars, at = [], [], []
    for x in C:
        b = bucket(x[0], sec)
        if not keys or keys[-1] != b:
            keys.append(b); bars.append([x[0], x[1], x[2], x[3], x[4], x[5]])
        else:
            y = bars[-1]; y[2] = max(y[2], x[2]); y[3] = min(y[3], x[3]); y[4] = x[4]; y[5] += x[5]
        at.append((len(bars) - 1, list(bars[-1])))   # snapshot of the developing bar at this chart bar's close
    return bars, at

def dev_ema(closes_completed, j, cur, n, a_cache):
    """EMA(n) on an HTF series where bar j is still forming with close `cur`."""
    prev = a_cache[j - 1] if j >= 1 else NA
    if prev is NA:
        return NA
    a = 2 / (n + 1)
    return a * cur + (1 - a) * prev

def trend_series(sec):
    bars, at = htf_bars(sec)
    cl = [b[4] for b in bars]
    e20, e50 = ema(cl, 20), ema(cl, 50)
    out = []
    for i, (j, dev) in enumerate(at):
        f, s = dev_ema(cl, j, dev[4], 20, e20), dev_ema(cl, j, dev[4], 50, e50)
        out.append(NA if f is NA or s is NA else (1 if f > s else -1))
    return out

def trend_m1():
    cl = [b[4] for b in M1]; e20, e50 = ema(cl, 20), ema(cl, 50); ts = [b[0] for b in M1]
    out = []
    for x in C:
        k = bisect.bisect_right(ts, x[0] + TF - 60) - 1      # the last 1m bar inside this 5m bar
        if k < 0 or ts[k] < x[0] or e20[k] is NA or e50[k] is NA:
            out.append(NA)
        else:
            out.append(1 if e20[k] > e50[k] else -1)
    return out

def trend_daily():
    days = {bucket(b[0] + 12 * 3600, 86400): b[4] for b in D1}  # Yahoo daily stamps are the session date
    keys = sorted(days); cl = [days[k] for k in keys]
    e20, e50 = ema(cl, 20), ema(cl, 50)
    out = []
    for x in C:
        j = bisect.bisect_left(keys, bucket(x[0], 86400))     # today's (forming) daily bar
        if j < 1 or e20[j - 1] is NA or e50[j - 1] is NA:
            out.append(NA); continue
        f = 2 / 21 * x[4] + (1 - 2 / 21) * e20[j - 1]; s = 2 / 51 * x[4] + (1 - 2 / 51) * e50[j - 1]
        out.append(1 if f > s else -1)
    return out

CHART_TR = [NA if E20[i] is NA or E50[i] is NA else (1 if E20[i] > E50[i] else -1) for i in range(N)]
TR = {
    'M1': CHART_TR if TF == 60 else trend_m1(),
    'M5': CHART_TR if TF == 300 else trend_series(300),
    'M15': trend_series(900), 'M30': trend_series(1800), 'H4': trend_series(14400), 'D': trend_daily(),
}
UPPER = 'M15' if TF == 60 else 'M30'   # 1 -> 15, 5 -> 30 (783-793)


# ---------------------------------------------------------------- POC (206-278)
import numpy as np
def poc(o, h, l, c, v, n, end):
    """POC_Calculate(n) evaluated with bar `end` as the last bar (numpy version of the loop below)."""
    if end - n + 1 < 0:
        return NA
    sl = slice(end - n + 1, end + 1)
    O_, H_, L_, C_, V_ = (np.asarray(a[sl], dtype=float) for a in (o, h, l, c, v))
    top, bot = H_.max(), L_.min(); step = (top - bot) / 24
    if step <= 0:
        return NA
    lv = bot + step * np.arange(25); lo_, hi_ = lv[:-1][:, None], lv[1:][:, None]
    bt, bb = np.maximum(C_, O_), np.minimum(C_, O_)
    tw, bw, body = H_ - bt, bb - L_, bt - bb
    den = 2 * tw + 2 * bw + body
    with np.errstate(divide='ignore', invalid='ignore'):
        def gv(y1, y2, height, vol):   # channel overlap with [y1, y2] (y1 <= y2), spread by height
            ov = np.clip(np.minimum(hi_, y2) - np.maximum(lo_, y1), 0, None)
            r = ov * np.where(height > 0, vol / np.where(height > 0, height, 1), 0)
            return np.nan_to_num(r)
        ok = den > 0
        bodyv = np.where(ok, body * V_ / np.where(ok, den, 1), 0); twv = np.where(ok, 2 * tw * V_ / np.where(ok, den, 1), 0); bwv = np.where(ok, 2 * bw * V_ / np.where(ok, den, 1), 0)
        tot = (gv(bb, bt, body, bodyv) + gv(bt, H_, tw, twv) + gv(L_, bb, bw, bwv)).sum(axis=1)
    p = int(np.argmax(tot))
    return float((lv[p] + lv[p + 1]) / 2)

def poc_loop(o, h, l, c, v, n, end):
    """POC_Calculate(n) evaluated with bar `end` as the last bar."""
    if end - n + 1 < 0:
        return NA
    cnum = 24
    top = max(h[end - n + 1:end + 1]); bot = min(l[end - n + 1:end + 1])
    step = (top - bot) / cnum
    if step <= 0:
        return NA
    lv = [bot + step * x for x in range(cnum + 1)]
    tot = [0.0] * cnum
    def gv(y11, y12, y21, y22, height, vol):
        if not height:
            return 0.0
        return max(min(max(y11, y12), max(y21, y22)) - max(min(y11, y12), min(y21, y22)), 0) * vol / height
    for b in range(end - n + 1, end + 1):
        bt, bb = max(c[b], o[b]), min(c[b], o[b])
        tw, bw, body = h[b] - bt, bb - l[b], bt - bb
        den = 2 * tw + 2 * bw + body
        if den <= 0:
            continue
        bodyv, twv, bwv = body * v[b] / den, 2 * tw * v[b] / den, 2 * bw * v[b] / den
        for x in range(cnum):
            tot[x] += gv(lv[x], lv[x + 1], bb, bt, body, bodyv) + gv(lv[x], lv[x + 1], bt, h[b], tw, twv) + gv(lv[x], lv[x + 1], bb, l[b], bw, bwv)
    p = tot.index(max(tot))
    return (lv[p] + lv[p + 1]) / 2

class Lazy:
    """Computed only for the bars we use (signals + setup windows): POC on every bar is slow in Python."""
    def __init__(self, fn): self.fn, self.c = fn, {}
    def __getitem__(self, i):
        if i not in self.c: self.c[i] = self.fn(i)
        return self.c[i]

def htf_poc(sec, n=24):
    bars, at = htf_bars(sec)
    def one(i):
        j, dev = at[i]
        if j < n - 1:
            return NA
        win = bars[j - n + 1:j] + [dev]
        return poc([b[1] for b in win], [b[2] for b in win], [b[3] for b in win], [b[4] for b in win], [b[5] for b in win], n, n - 1)
    return Lazy(one)

BBARS = math.floor(360 / (TF // 60))   # 72 on M5 (308-316)
POC_CHART = Lazy(lambda i: poc(O, Hh, L, CL, V, BBARS, i))
POC_TBL = {name: htf_poc(sec) for name, sec in (('M15', 900), ('M30', 1800), ('H1', 3600))}


# ---------------------------------------------------------------- support & resistance (465-594)
def sr():
    atrMovement, lookback, maxZoneSize = 1.0, 25, 2.5
    hb = [max(O[i], CL[i]) for i in range(N)]; lb = [min(O[i], CL[i]) for i in range(N)]
    res1 = res2 = sup1 = sup2 = 0.0
    lfr = lfs = True
    atrSaved = 0.0; pR1 = pR2 = pS1 = pS2 = 0.0
    R, S = [NA] * N, [NA] * N
    lt = lambda a, b: a is not NA and b is not NA and a < b
    for i in range(N):
        a = ATR[i]
        if i >= lookback and a:
            if Hh[i - 1] == max(Hh[i - lookback + 1:i + 1]) and Hh[i] < Hh[i - 1] and lfr:
                r1 = Hh[i - 1]; r2 = hb[i - 2] if hb[i - 2] > hb[i - 1] else (hb[i] if hb[i] > hb[i - 1] else hb[i - 1])
                if (r1 - r2) / a <= maxZoneSize:
                    lfr = False; pR1, pR2, atrSaved = r1, r2, a
            if L[i - 1] == min(L[i - lookback + 1:i + 1]) and L[i] > L[i - 1] and lfs:
                s1 = L[i - 1]; s2 = lb[i - 2] if lb[i - 2] < lb[i - 1] else (lb[i] if lb[i] < lb[i - 1] else lb[i - 1])
                if (s2 - s1) / a <= maxZoneSize:
                    lfs = False; pS1, pS2, atrSaved = s1, s2, a
        if lt(pR1, CL[i]): pR1 = pR2 = NA
        if lt(CL[i], pS1): pS1 = pS2 = NA
        if pR1 is not NA and pR1 - L[i] >= atrSaved * atrMovement:
            res1, res2 = pR1, pR2; pR1 = pR2 = NA
        if pS1 is not NA and Hh[i] - pS1 >= atrSaved * atrMovement:
            sup1, sup2 = pS1, pS2; pS1 = pS2 = NA
        if CL[i] >= res1: lfr = lfs = True
        if CL[i] <= sup1: lfs = lfr = True
        R[i], S[i] = res1, sup1
    return R, S
RES, SUP = sr()


# ---------------------------------------------------------------- stars: zigzag (621-696)
def zigzag(depth, dev, back):
    """Per bar: the star the script draws on that bar (pos, high?) and whether it stays (the leg ended)."""
    last_h = last_l = lw = hg = 1
    downs, highing_s, lowing_s, lh_s, ll_s, labels = [], [], [], [], [], []
    lowing_prev = highing_prev = NA
    since_not_h = since_not_l = since_not_dn = NA
    for i in range(N):
        lw += 1; hg += 1; last_h += 1; last_l += 1
        if i < depth:
            downs.append(NA); labels.append(NA); continue
        lo_win = L[i - depth + 1:i + 1]; hi_win = Hh[i - depth + 1:i + 1]
        mn, mx = min(lo_win), max(hi_win)
        p_lw = min(k for k in range(depth) if L[i - k] == mn)     # most recent extreme, like ta.lowestbars
        p_hg = min(k for k in range(depth) if Hh[i - k] == mx)
        lowing = lw == p_lw or L[i] - L[i - p_lw] > dev * MINTICK
        highing = hg == p_hg or Hh[i - p_hg] - Hh[i] > dev * MINTICK
        # ta.barssince(not highing[1]) / (not lowing[1])
        since_not_h = NA if highing_prev is NA else (0 if not highing_prev else (NA if since_not_h is NA else since_not_h + 1))
        since_not_l = NA if lowing_prev is NA else (0 if not lowing_prev else (NA if since_not_l is NA else since_not_l + 1))
        lh, ll = since_not_h, since_not_l
        notgt = NA if (lh is NA or ll is NA) else not (lh > ll)       # na counts as false in ta.barssince
        since_not_dn = 0 if notgt is True else (NA if since_not_dn is NA else since_not_dn + 1)
        down = since_not_dn is not NA and since_not_dn >= back
        down_prev = downs[-1] if downs else NA
        lower = (i - lw >= 0) and L[i - lw] > L[i - p_lw]
        higher = (i - hg >= 0) and Hh[i - hg] < Hh[i - p_hg]
        if lw != p_lw and ((down_prev is NA or not down_prev) or lower):
            lw = p_lw if p_lw < hg else 0
        if hg != p_hg and ((down_prev is not NA and down_prev) or higher):
            hg = p_hg if p_hg < lw else 0
        x1 = lw if down else hg
        if down_prev is not NA and down != down_prev:
            if down: last_h = hg
            else: last_l = lw
        labels.append((i - x1, not down))   # star at a high when not down, at a low when down
        downs.append(down)
        highing_prev, lowing_prev = highing, lowing
    keep = [labels[i] is not NA and i + 1 < N and downs[i + 1] is not NA and downs[i + 1] != downs[i] for i in range(N)]
    return labels, keep

print('stars...', flush=True)
ZZ = [zigzag(5, 1, 3), zigzag(13, 8, 5), zigzag(34, 13, 8)]
CODES = [(1, 2), (3, 4), (7, 8)]   # (high, low): small yellow, medium blue, large red / lime


# ---------------------------------------------------------------- Killshot signals + confirmations (812-901)
SIG = []
for i in range(1, N):
    if None in (E20[i], E50[i], E20[i - 1], E50[i - 1], E238[i]):
        continue
    up = E20[i - 1] <= E50[i - 1] and E20[i] > E50[i]
    dn = E20[i - 1] >= E50[i - 1] and E20[i] < E50[i]
    if not (up or dn):
        continue
    d = 1 if up else -1
    cf = {
        'candle': (CL[i] > O[i]) if up else (CL[i] < O[i]),
        'time': SESS[i],
        'behind': (CL[i] > E238[i]) if up else (CL[i] < E238[i]),
        'trend': TR[UPPER][i] == d,
        'poc': POC_CHART[i] is not NA and ((POC_CHART[i] < CL[i]) if up else (POC_CHART[i] > CL[i])),
    }
    SIG.append((i, d, cf))
full = [s for s in SIG if all(s[2].values())]
print('crosses', len(SIG), 'in trade time', sum(1 for s in SIG if s[2]['time']), 'fully confirmed', len(full))


# ---------------------------------------------------------------- setups
BEFORE, AFTER_MAX = 130, 60   # rounds stay short: only trades that finish within an hour of 1m bars
TBL = ['M1', 'M5', 'M15', 'M30', 'H4', 'D']
def flags(k):
    b = 0
    for j, name in enumerate(TBL):
        if TR[name][k] == 1: b |= 1 << j
        if TR[name][k] is NA: b |= 1 << (10 + j)          # unknown: drawn as a blank cell
    for j, name in enumerate(('M15', 'M30', 'H1')):
        p = POC_TBL[name][k]
        if p is not NA and CL[k] > p: b |= 1 << (6 + j)
    if SESS[k]: b |= 1 << 9
    return b

BT = {'n': 0, 'win': 0}
setups = []
for i, d, cf in full:
    if i < BEFORE + 300 or not ATR[i]:
        continue
    # Jay: don't chase the arrow. Wait for price to come back and test the line (20 EMA), enter there.
    fill = None
    for j in range(i + 1, min(N, i + WAIT_MAX)):
        if (d == 1 and E20[j] < E50[j]) or (d == -1 and E20[j] > E50[j]):
            break                                    # trend flipped before the test: no trade
        if (d == 1 and L[j] <= E20[j]) or (d == -1 and Hh[j] >= E20[j]):
            fill = j; break
    if fill is None:
        continue
    a = ATR[fill - 1]                                # known when the order fills
    entry = min(O[fill], E20[fill]) if d == 1 else max(O[fill], E20[fill])   # limit at the line (or the open if it gapped through)
    stop = entry - d * STOP_ATR * a
    r = abs(entry - stop)
    tgt = entry + d * RR * r
    out = None
    for j in range(fill, min(N, fill + AFTER_MAX)):
        hs = L[j] <= stop if d == 1 else Hh[j] >= stop
        ht = j > fill and (Hh[j] >= tgt if d == 1 else L[j] <= tgt)
        if hs: out = ('loss', j); break
        if ht: out = ('win', j); break
    if not out:
        continue
    BT['n'] += 1; BT['win'] += out[0] == 'win'
    a0, b0 = i - BEFORE, min(N, out[1] + 10)
    if fill - i > 40: continue   # keep the wait short enough to watch
    if any(C[k + 1][0] - C[k][0] > 3 * 3600 for k in range(a0, b0 - 1)):   # no weekend inside (the 1h daily break is fine, TV shows it too)
        continue
    f2 = lambda x: None if x is NA else round(x, 2)
    mk = []
    for z, (lab, keep) in enumerate(ZZ):
        for t in range(a0, b0):
            if keep[t] and a0 <= lab[t][0] < b0:
                mk.append([lab[t][0] - a0, CODES[z][0] if lab[t][1] else CODES[z][1], t - a0])
    for k in range(a0, b0):
        if k == i:
            continue
        if E20[k - 1] <= E50[k - 1] and E20[k] > E50[k] and SESS[k]: mk.append([k - a0, 5, k - a0])
        if E20[k - 1] >= E50[k - 1] and E20[k] < E50[k] and SESS[k]: mk.append([k - a0, 6, k - a0])
    # the current (repainting) star of each depth, per bar: [pos, high?] x3
    zt = [[(ZZ[z][0][k][0] - a0, 1 if ZZ[z][0][k][1] else 0) if ZZ[z][0][k] is not NA else (-1, 0) for z in range(3)] for k in range(a0, b0)]
    zt = [[v for p in row for v in p] for row in zt]
    # S/R as plotted: a run of bars with the same level (linebr breaks on a change), coloured by close
    ln = []
    for arr, kind in ((RES, 1), (SUP, -1)):
        k = a0 + 1
        while k < b0:
            if arr[k] is NA or arr[k] != arr[k - 1] or not arr[k]:
                k += 1; continue
            k2 = k
            while k2 + 1 < b0 and arr[k2 + 1] == arr[k]:
                k2 += 1
            ln.append([k - 1 - a0, round(arr[k], 2), k2 - a0, kind])
            k = k2 + 1
    setups.append({
        'v': 2, 'sym': 'GOLD', 'tf': TF, 'd': d, 'at': BEFORE, 'entry': f2(entry), 'stop': f2(stop), 'target': f2(tgt), 'rr': RR,
        'result': out[0], 't0': C[a0][0], 'upper': UPPER, 'fill': fill - a0,
        'cf': {'candle': 1, 'time': 1, 'behind': 1, 'trend': 1, 'poc': 1},
        'c': [[f2(O[k]), f2(Hh[k]), f2(L[k]), f2(CL[k])] for k in range(a0, b0)],
        'e': [[f2(E20[k]), f2(E50[k]), f2(E238[k])] for k in range(a0, b0)],
        'p': [None if POC_CHART[k] is NA else round(POC_CHART[k], 1) for k in range(a0, b0)],
        'f': [flags(k) for k in range(a0, b0)],
        'mk': mk, 'zt': zt, 'ln': ln,
    })

w = [s for s in setups if s['result'] == 'win']
print('backtest (all setups that filled, any length):', BT); lo = [s for s in setups if s['result'] == 'loss']
print('setups', len(setups), 'wins', len(w), 'losses', len(lo))
random.seed(11); random.shuffle(w); random.shuffle(lo)
# Gold mostly fell over these weeks (sells outnumber buys ~3:1), so keep every buy and fill up with sells.
# The game deals 3 wins + 2 losses a day, at least one of them a buy (the real 1:1 hit rate is ~54%).
pick = lambda arr, n: [x for x in arr if x['d'] == 1][:n] + [x for x in arr if x['d'] == -1][:n]
pool = pick(w, 8)[:16] + pick(lo, 6)[:12]
for n_, s in enumerate(pool):
    s['id'] = n_
if '--dry' not in sys.argv:
    json.dump(pool, open(OUT, 'w'), separators=(',', ':'))
    print('wrote', os.path.relpath(OUT), os.path.getsize(OUT), 'bytes,', len(pool), 'setups')

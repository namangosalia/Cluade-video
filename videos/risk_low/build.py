"""Podcast clips 4.1.1 + 4.1.2 (Gunjan Talks): risk comes down to moderate / low -> explainer reel.

- the original 16:9 podcast frame, uncropped (podcast logo kept as it is), on a deep-navy explainer page
  styled after Naman's "Longitudinal Cardiovascular Prevention" artwork; no AnginaX logo
- small white captions underneath the picture, key words highlighted, word by word
- an animated risk-trajectory chart (High -> Moderate -> Low, then maintained) under the captions,
  then a 3-step card for "go to your doctor / get your tests done / do your AnginaX"
- cuts: "So, and then how are we going to tell everybody is like" and "Educate them if they don't know."
  (plus "you know," and every hesitation gap); each join checked by transcribing it
"""
import json, os, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "risk_to_low_9x16.mp4")
W, H, FPS = 1080, 1920, 25
INTER = "/usr/share/fonts/opentype/inter/"
SERIF = os.path.join(REPO, "assets", "fonts", "playfair-display-latin-500-normal.woff")
BLUE, GOLD, WHITE = (112, 182, 255), (206, 176, 118), (255, 255, 255)
RED, AMBER, GREEN, TEAL = (232, 76, 80), (240, 196, 72), (96, 214, 120), (80, 220, 230)

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)
def F(name, size): return ImageFont.truetype(INTER + name, size)

# ---------------------------------------------------------------- sources, words, cuts
parts = [os.path.join(HERE, "raw", f"part{i}.mp4") for i in (1, 2)]
lst = os.path.join(TMP, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
comb = os.path.join(TMP, "combined.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", comb], check=True)
words = json.load(open(os.path.join(HERE, "words.json")))
wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a16 = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
DUR = len(a16) / 16000
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
SIL = min(-30.0, float(np.percentile(rms[rms > -90], 90)) - 20.0)
MIN_PAUSE, KEEP, KEEP_LONG = 0.16, 0.12, 0.24
ends = [wd[1] for wd in words if wd[2].strip().endswith((".", "?", "!"))]
cuts, s_ = [], None
for i, q in enumerate(np.append(rms < SIL, False)):
    if q and s_ is None: s_ = i
    if not q and s_ is not None:
        q0, q1 = s_ / 100, i / 100
        if q1 - q0 >= MIN_PAUSE:
            k = KEEP_LONG if any(e - 0.2 <= q0 <= e + 0.35 for e in ends) else KEEP
            if q1 - q0 > k: cuts.append((q0 + k / 2, q1 - k / 2))
        s_ = None
CUT_TIMES = [(4.58, 5.12),      # "you know,"
             (11.62, 16.16),    # "So, and then how are we going to tell everybody is like"
             (30.52, 31.10),    # stutter: "I want my, I want to do my AnginaX" -> "I want to do my AnginaX"
             (32.62, 34.42),    # "Educate them if they don't know."
             (36.56, 37.25)]    # "all right," between "...completely." and "But this is how..."
cuts += CUT_TIMES
END_T = words[-1][1] + 0.30
cuts.append((END_T, DUR + 1))
cuts.sort(); merged = []
for s, e in cuts:
    if merged and s <= merged[-1][1]: merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
    else: merged.append((s, e))
keep, t0 = [], 0.0
for s, e in merged:
    if s - t0 > 0.04: keep.append((t0, min(s, DUR)))
    t0 = e
BODY = sum(e - s for s, e in keep)
def remap(t):
    acc = 0.0
    for s, e in keep:
        if t < s: return acc
        if t <= e: return acc + t - s
        acc += e - s
    return acc
def unmap(tn):
    acc = 0.0
    for s, e in keep:
        if tn <= acc + (e - s): return s + tn - acc
        acc += e - s
    return keep[-1][1]
TW = lambda i: remap(words[i][0])
OUTRO = 1.6
TOTAL = BODY + OUTRO
print(f"{len(keep)} pieces, body {BODY:.1f}s (raw {DUR:.1f}s)")

# ---------------------------------------------------------------- page layout
PX, PY, PWD = 40, 400, 1000                    # the podcast picture (16:9, uncropped), rounded
PHT = int(PWD * 9 / 16)
CAP_Y = PY + PHT + 30
CARD = (40, 1150, 1000, 430)                   # chart / steps card under the captions

def page():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    top = np.array([30, 46, 76], np.float32); bot = np.array([8, 14, 28], np.float32)
    g = (yy / H)[..., None]
    bg = top * (1 - g) + bot * g
    glow = np.exp(-(((xx - 200) / 520) ** 2 + ((yy - 260) / 420) ** 2))[..., None] * np.array([60, 80, 110], np.float32)
    glow2 = np.exp(-(((xx - 900) / 500) ** 2 + ((yy - 1500) / 500) ** 2))[..., None] * np.array([20, 40, 80], np.float32)
    img = Image.fromarray(np.clip(bg + glow + glow2, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    lab = F("Inter-Medium.otf", 24); x = 64
    for ch in "LONGITUDINAL CARE":
        d.text((x, 150), ch, font=lab, fill=(220, 226, 236, 255)); x += d.textlength(ch, font=lab) + 7
    d.line((64, 192, 150, 192), fill=GOLD + (255,), width=3)
    sf = ImageFont.truetype(SERIF, 62)
    d.text((62, 214), "Longitudinal Cardiovascular", font=sf, fill=WHITE + (255,))
    d.text((62, 290), "Prevention.", font=sf, fill=BLUE + (255,))
    # rounded frame shadow for the picture
    sh = Image.new("L", (W, H), 0); ImageDraw.Draw(sh).rounded_rectangle((PX, PY + 10, PX + PWD, PY + PHT + 10), 26, fill=150)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
    img = Image.alpha_composite(img, shadow)
    return np.asarray(img.convert("RGB")).astype(np.float32)
PAGE = page()
MASK = Image.new("L", (PWD, PHT), 0); ImageDraw.Draw(MASK).rounded_rectangle((0, 0, PWD - 1, PHT - 1), 26, fill=255)
MASK = (np.asarray(MASK).astype(np.float32) / 255)[..., None]

def glass(wd, ht):
    img = Image.new("RGBA", (wd, ht), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, wd - 1, ht - 1), 30, fill=(24, 40, 66, 150), outline=(130, 170, 220, 90), width=2)
    return img

# ---------------------------------------------------------------- risk trajectory chart (animated)
CW_, CH_ = CARD[2], CARD[3]
AX0, AX1, AY0, AY1 = 120, 950, 150, 360          # plot area inside the card (x0, x1, y_top, y_bottom)
XS = {"Baseline": 0.06, "3 Months": 0.30, "6 Months": 0.48, "12 Months": 0.66, "24 Months": 0.93}
KX = np.array([0.0, 0.06, 0.30, 0.48, 0.66, 0.93, 0.99]); KY = np.array([84, 80, 50, 34, 26, 22, 22])
def px(xf): return AX0 + (AX1 - AX0) * xf
def py(v): return AY1 - (AY1 - AY0) * v / 100
CURVE_X = np.linspace(0, 0.99, 400)
from scipy.interpolate import PchipInterpolator
CURVE_Y = PchipInterpolator(KX, KY)(CURVE_X)
def risk_col(v):
    stops = [(80, RED), (50, AMBER), (26, GREEN), (18, TEAL)]
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        if v >= v1:
            k = (v0 - v) / (v0 - v1); k = min(max(k, 0), 1)
            return tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
    return TEAL

def chart_base():
    img = glass(CW_, CH_); d = ImageDraw.Draw(img)
    d.text((44, 30), "Risk Trajectory", font=F("Inter-SemiBold.otf", 36), fill=WHITE + (255,))
    d.text((44, 78), "How cardiovascular risk improves with regular follow-up", font=F("Inter-Regular.otf", 25), fill=(200, 212, 230, 255))
    sm = F("Inter-Regular.otf", 21)
    for v in (0, 20, 40, 60, 80, 100):
        d.text((AX0 - 16, py(v)), str(v), font=sm, fill=(190, 200, 215, 255), anchor="rm")
    d.line((AX0, AY0 - 6, AX0, AY1), fill=(190, 205, 225, 160), width=2); d.line((AX0, AY1, AX1 + 20, AY1), fill=(190, 205, 225, 160), width=2)
    for lab, xf in XS.items():
        d.line((px(xf), AY1, px(xf), AY1 + 6), fill=(190, 205, 225, 160), width=2)
        d.text((px(xf), AY1 + 22), lab, font=F("Inter-Medium.otf", 21), fill=(225, 232, 242, 255), anchor="mm")
    return img
CHART_BASE = chart_base()

def pill(d, x, y, text, col, a):
    f = F("Inter-Medium.otf", 24); tw_ = d.textlength(text, font=f)
    d.rounded_rectangle((x - tw_ / 2 - 18, y - 22, x + tw_ / 2 + 18, y + 22), 22,
                        fill=tuple(int(c * 0.35) for c in col) + (int(230 * a),), outline=col + (int(255 * a),), width=2)
    d.text((x, y), text, font=f, fill=(255, 255, 255, int(255 * a)), anchor="mm")

def chart_frame(prog, pills, pulse=0.0):
    """prog: how far the curve is drawn (fraction of x); pills: {name: alpha}"""
    img = CHART_BASE.copy()
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    n = int(np.searchsorted(CURVE_X, prog))
    pts = [(px(x), py(y)) for x, y in zip(CURVE_X[:n], CURVE_Y[:n])]
    # soft fill under the drawn curve
    if n > 2:
        poly = pts + [(pts[-1][0], AY1), (pts[0][0], AY1)]
        fill = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(fill).polygon(poly, fill=(120, 170, 230, 40))
        lay = Image.alpha_composite(lay, fill); d = ImageDraw.Draw(lay)
    for i in range(1, len(pts)):
        d.line((pts[i - 1], pts[i]), fill=risk_col(CURVE_Y[i]) + (255,), width=6)
    glow = lay.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img, glow); img = Image.alpha_composite(img, lay); d = ImageDraw.Draw(img)
    if n > 1 and prog > 0.95:                                     # arrow head: maintained
        x1, y1 = pts[-1]; d.polygon([(x1 + 14, y1), (x1 - 4, y1 - 10), (x1 - 4, y1 + 10)], fill=TEAL + (255,))
    for name, xf, v, col, dy in (("High Risk", 0.06, 80, RED, -48), ("Moderate Risk", 0.30, 50, AMBER, -46),
                                 ("Low Risk", 0.66, 26, GREEN, -44)):
        a = pills.get(name, 0.0)
        if a <= 0: continue
        cx, cy = px(xf), py(v)
        r = 10 + (6 * pulse if name == "Low Risk" else 0)
        d.ellipse((cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4), fill=col + (int(90 * a),))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, int(255 * a)), outline=col + (int(255 * a),), width=4)
        d.line((cx, cy + r, cx, AY1), fill=(220, 230, 245, int(110 * a)), width=1)
        pill(d, cx + (40 if name == "High Risk" else 0), cy + dy, name, col, a)
    return np.asarray(img).astype(np.float32) / 255

# ---------------------------------------------------------------- steps card (part 2)
STEPS = [(62, "Go to your doctor", "Any doctor you prefer, or your family doctor"),
         (73, "Get your tests done", "Your regular check-up tests"),
         (77, "Do your AnginaX", "If your doctor doesn't have it, ask for it")]
def steps_frame(active):
    """active: list of alpha per step (0..1)"""
    img = glass(CW_, CH_); d = ImageDraw.Draw(img)
    d.text((44, 30), "What you can do", font=F("Inter-SemiBold.otf", 36), fill=WHITE + (255,))
    for i, (wi, t1, t2) in enumerate(STEPS):
        a = active[i]; y = 110 + i * 100
        on = tuple(int(150 + (c - 150) * a) for c in BLUE)
        d.ellipse((44, y, 104, y + 60), fill=(int(20 + 92 * a), int(34 + 148 * a), int(60 + 195 * a), 255))
        d.text((74, y + 30), str(i + 1), font=F("Inter-Bold.otf", 30), fill=(12, 20, 36, 255) if a > 0.5 else (200, 210, 225, 255), anchor="mm")
        d.text((130, y + 2), t1, font=F("Inter-SemiBold.otf", 32), fill=(255, 255, 255, int(110 + 145 * a)))
        d.text((130, y + 42), t2, font=F("Inter-Regular.otf", 23), fill=(200, 212, 230, int(90 + 165 * a)))
    return np.asarray(img).astype(np.float32) / 255

# ---------------------------------------------------------------- captions (small white, highlighted words)
F_BODY = F("Inter-Medium.otf", 44); F_HL = F("Inter-Bold.otf", 44)
MAXW, LH = 960, 58
GROUPS = [
    (0, 11, "What we have seen is, over a period of [9 months,]"),
    (11, 16, "like every [3–6 months,]"),
    (18, 25, "there's a [follow-up] for those patients,"),
    (25, 35, "and the risk has come down to [moderate] or [low.]"),
    (47, 55, "We want to reduce everyone's risk to [low]"),
    (55, 62, "and let them [maintain low risk.]"),
    (62, 70, "Just go to [any doctor] that you prefer,"),
    (70, 73, "your [family doctor.]"),
    (73, 77, "Get your [tests done.]"),
    (77, 80, "Do your [AnginaX.]"),
    (80, 86, "If your doctors don't have it,"),
    (86, 96, "call them up and say, “I want to do my [AnginaX.]”"),
    (102, 109, "Eventually, this will be in [India] completely."),
    (109, 118, "But this is how we're going to [save lives.]"),
]
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
SPACE = dd.textlength(" ", font=F_BODY)
def tokens(text):
    out, hl = [], False
    for raw in text.split():
        if raw.startswith("[") or raw.startswith("“["): hl = True
        out.append((raw.replace("[", "").replace("]", ""), hl))
        if raw.rstrip(".,”").endswith("]") or raw.endswith("]"): hl = False
    return out
def tw(word, h): return dd.textlength(word, font=F_HL if h else F_BODY)
def layout(toks):
    widths = [tw(t, h) for t, h in toks]
    total = sum(widths) + SPACE * (len(toks) - 1)
    lines = [list(range(len(toks)))]
    if total > MAXW:
        best = None
        for k in range(1, len(toks)):
            la = sum(widths[:k]) + SPACE * (k - 1); lb = sum(widths[k:]) + SPACE * (len(toks) - k - 1)
            if max(la, lb) <= MAXW and (best is None or abs(la - lb) < best[0]): best = (abs(la - lb), k)
        k = best[1] if best else len(toks) // 2
        lines = [list(range(k)), list(range(k, len(toks)))]
    pos = []
    for li, idx in enumerate(lines):
        lw = sum(widths[i] for i in idx) + SPACE * (len(idx) - 1); x = (W - lw) / 2
        for i in idx:
            pos.append((x, li * LH, toks[i][0], toks[i][1])); x += widths[i] + SPACE
    return pos
def word_layer(word, hl):
    f = F_HL if hl else F_BODY
    img = Image.new("RGBA", (int(tw(word, hl)) + 40, 86), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).text((20, 14), word, font=f, fill=170)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(6)))
    img = Image.alpha_composite(img, shadow)
    ImageDraw.Draw(img).text((20, 10), word, font=f, fill=(BLUE if hl else WHITE) + (255,))
    return np.asarray(img).astype(np.float32) / 255
caps = []
for gi, (i0, i1, text) in enumerate(GROUPS):
    toks = tokens(text); n_w = i1 - i0
    times = [TW(i0 + min(int(round(j * n_w / len(toks))), n_w - 1)) for j in range(len(toks))]
    end = remap(words[i1 - 1][1]) + 0.6
    if gi + 1 < len(GROUPS):
        nx = TW(GROUPS[gi + 1][0]) - 0.04
        if nx - end < 0.6: end = nx
    caps.append((times[0], end, [(t, x, y, word_layer(wd, h)) for t, (x, y, wd, h) in zip(times, layout(toks))]))

# ---------------------------------------------------------------- card state over time
T_HIGH = TW(20)                      # "follow-up": baseline High Risk appears
T_DRAW0, T_MOD, T_LOW = TW(27), TW(32), TW(34)     # curve: risk ... moderate ... low
T_PULSE = TW(54)                     # "...risk to low"
T_MAINT = TW(58)                     # "maintain": the line carries on, flat and low
T_STEPS = TW(62) - 0.3               # chart gives way to the steps card
def card_at(t):
    if t < T_STEPS:
        if t < T_DRAW0: prog = 0.06 * ease((t - T_HIGH) / 0.6)
        elif t < T_MOD: prog = 0.06 + 0.24 * ease((t - T_DRAW0) / (T_MOD - T_DRAW0))
        elif t < T_LOW: prog = 0.30 + 0.36 * ease((t - T_MOD) / (T_LOW - T_MOD + 0.3))
        elif t < T_MAINT: prog = 0.66
        else: prog = 0.66 + 0.33 * ease((t - T_MAINT) / 1.8)
        prog = max(prog, 0.66 if t >= T_LOW + 0.3 else prog)
        pills = {"High Risk": ease((t - T_HIGH) / 0.5), "Moderate Risk": ease((t - T_MOD) / 0.4),
                 "Low Risk": ease((t - T_LOW) / 0.4)}
        pulse = max(0.0, np.sin(min(1, max(0, (t - T_PULSE) / 1.2)) * np.pi))
        return chart_frame(prog, pills, pulse), 1.0
    act = [ease((t - TW(wi)) / 0.4) for wi, _, _ in STEPS]
    return steps_frame(act), ease((t - T_STEPS) / 0.5)

# ---------------------------------------------------------------- audio
cutwav = os.path.join(TMP, "cut.wav")
fc_a = "".join(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:st={max(0, e - s - 0.015):.3f}:d=0.015[a{i}];"
               for i, (s, e) in enumerate(keep)) + "".join(f"[a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=0:a=1[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-filter_complex", fc_a, "-map", "[a]", "-ar", "48000", cutwav], check=True)
VOICE = ("highpass=f=70,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2.5,highshelf=f=9000:g=1.5,"
         "deesser=i=0.3,acompressor=threshold=0.1:ratio=2.5:attack=8:release=150:makeup=1.5,"
         f"apad=pad_dur={OUTRO + 0.2},loudnorm=I=-14:TP=-1:LRA=7")

# ---------------------------------------------------------------- render
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", comb, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
SW, SH = 1280, 720
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", cutwav, "-map", "0:v", "-map", "1:a", "-af", VOICE, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                        "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", OUT],
                       stdin=subprocess.PIPE)
src_idx, cur = -1, None
def src_frame(k):
    global src_idx, cur
    while src_idx < k:
        b = dec.stdout.read(SW * SH * 3)
        if len(b) < SW * SH * 3: break
        cur = np.frombuffer(b, np.uint8).reshape(SH, SW, 3); src_idx += 1
    return cur
def over(fr, L, x, y, a=1.0):
    h_, w_ = L.shape[:2]; sub = fr[y:y + h_, x:x + w_]; al = L[: sub.shape[0], : sub.shape[1], 3:4] * a
    sub[:] = sub * (1 - al) + L[: sub.shape[0], : sub.shape[1], :3] * 255 * al

pic_last = None
for fi in range(int(round(TOTAL * FPS))):
    t = fi / FPS
    fr = PAGE.copy()
    tb = min(t, BODY - 1 / FPS)
    k = int(round(unmap(tb) * FPS))
    if t < BODY:
        pic_last = cv2.resize(src_frame(k), (PWD, PHT), interpolation=cv2.INTER_AREA).astype(np.float32)
    fade = 1 - ease((t - BODY - 0.6) / 0.9)                  # gentle fade of picture + cards after the last word
    sub = fr[PY:PY + PHT, PX:PX + PWD]
    sub[:] = sub * (1 - MASK * fade) + pic_last * MASK * fade
    L, ca = card_at(tb)
    if t < T_STEPS + 0.5 and t >= T_STEPS:                   # cross-fade chart -> steps
        Lc, _ = card_at(T_STEPS - 0.01); over(fr, Lc, CARD[0], CARD[1], (1 - ca) * fade)
    over(fr, L, CARD[0], CARD[1], ca * fade * ease(t / 0.6))
    for s, e, wl in caps:
        if s - 0.02 <= t < e:
            out = 1 - ease((t - (e - 0.2)) / 0.2)
            for tt_, x, y, LW in wl:
                if t >= tt_ - 0.02:
                    over(fr, LW, int(x) - 20, CAP_Y + y - 10, ease((t - tt_ + 0.02) / 0.16) * out)
            break
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", OUT)

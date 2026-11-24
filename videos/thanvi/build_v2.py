"""Dr Sunil Thanvi, in the style of the 'biggest pandemic' video (videos/oneliner/build_v2.py), as Naman asked
(his screen recording of it: style_reference.mp4):

- PRECAP: his strongest line first, graded dark black-and-white like a trailer:
  "we can stop it from becoming a health checkup person into a cardiac patient"
- a 2 s heart-monitor moment (green beats turn red and go flat), continuous crossfades, no black
- then the full answer: framings change on phrases (medium / close / split with a wider shot on top),
  small sentence captions low on screen, kinetic callouts on the left (tag + bold capitals, cyan accent,
  strikethrough, numbered list)
- the clips' burned-in captions stay out of frame (everything is cut from the clean area above them)
- audio: the noise-reduced voice from prep.py; small hesitation gaps trimmed; "it helps us," repeat removed
- AnginaX logo top right; ends on LEARN MORE for 1.7 s
"""
import json, os, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, ".tmp_v2"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "thanvi_trailer_style_9x16.mp4")
W, H, FPS = 1080, 1920, 30
POP = os.path.join(REPO, "assets", "fonts", "poppins-latin-800-normal.woff")
INTER = "/usr/share/fonts/opentype/inter/"
CYAN, WHITE = (52, 196, 240), (255, 255, 255)
CLEAN_H = 920                                     # source rows above the burned-in captions
def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- sources: picture from raw, cleaned voice from prepped
def concat(names, out):
    lst = out + ".txt"; open(lst, "w").write("".join(f"file '{n}'\n" for n in names))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
comb = os.path.join(TMP, "raw_comb.mp4"); concat([os.path.join(HERE, "raw", f"part{i}.mp4") for i in (1, 2, 3)], comb)
combp = os.path.join(TMP, "prep_comb.mp4"); concat([os.path.join(HERE, "prepped", f"part{i}.mp4") for i in (1, 2, 3)], combp)
words = json.load(open(os.path.join(HERE, "words.json")))
TW0 = lambda i: words[i][0]; TW1 = lambda i: words[i][1]
wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", combp, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a16 = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
DUR = len(a16) / 16000

# ---------------------------------------------------------------- edit
CLIPS = [(TW0(61) - 0.12, TW1(75) + 0.15),        # precap
         (0.0, TW1(224) + 0.35)]                    # the full answer
CUTS = [(56.85, 57.90)]                             # "it helps us, it suggests us" -> "it suggests us"
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
SIL = min(-30.0, float(np.percentile(rms[rms > -90], 90)) - 20.0)
ends = [wd[1] for wd in words if wd[2].strip().endswith((".", "?", "!"))]
s_ = None
for i, q in enumerate(np.append(rms < SIL, False)):
    if q and s_ is None: s_ = i
    if not q and s_ is not None:
        q0, q1 = s_ / 100, i / 100
        if q1 - q0 >= 0.30:
            k = 0.36 if any(e - 0.2 <= q0 <= e + 0.35 for e in ends) else 0.22
            if q1 - q0 > k: CUTS.append((q0 + k / 2, q1 - k / 2))
        s_ = None
ECG_LEAD, ECG_DUR, ECG_X = 0.10, 2.0, 0.40
timeline, t = [], 0.0
for ci, (c0, c1) in enumerate(CLIPS):
    if ci: t += ECG_LEAD + ECG_DUR - ECG_X
    t0 = c0
    for s, e in sorted(x for x in CUTS if c0 < x[0] < c1) + [(c1, c1)]:
        if s > t0 + 0.04: timeline.append((t, t + s - t0, t0, ci)); t += s - t0
        t0 = max(t0, e)
BODY = t
END_XF, CTA_HOLD = 0.4, 1.7
TOTAL = BODY + END_XF + CTA_HOLD
SPAN = {ci: ([x for x in timeline if x[3] == ci][0][0], [x for x in timeline if x[3] == ci][-1][1]) for ci in range(2)}
ECG_T0 = SPAN[0][1] + ECG_LEAD
def src_of(tn):
    best = None
    for o0, o1, s, ci in timeline:
        if o0 <= tn < o1: return s + tn - o0, ci
        if tn >= o1: best = (s + (o1 - o0) - 1 / FPS, ci)
    return best if best else (timeline[0][2], 0)
def out_of(src_t, clip):
    for o0, o1, s, ci in timeline:
        if ci == clip and s - 0.02 <= src_t <= s + (o1 - o0) + 0.02: return o0 + min(max(src_t - s, 0), o1 - o0)
    cand = [(s - src_t, o0) for o0, o1, s, ci in timeline if ci == clip and s > src_t]
    return min(cand)[1] if cand else SPAN[clip][1]
print(f"{len(timeline)} pieces, body {BODY:.1f}s")

# ---------------------------------------------------------------- face track (clean area), per shot
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(comb); SW, SH = int(cap.get(3)), int(cap.get(4))
faces, hists = [], []
while True:
    ok, f = cap.read()
    if not ok: break
    small = cv2.resize(f[:CLEAN_H], (SW // 2, CLEAN_H // 2), interpolation=cv2.INTER_AREA)
    hh = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256]); hists.append(cv2.normalize(hh, hh).flatten())
    d = fc.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(24, 24))
    faces.append(max(d, key=lambda b: b[2]) if len(d) else None)
N = len(hists)
shots = [0] + [k for k in range(1, N) if cv2.compareHist(hists[k - 1], hists[k], cv2.HISTCMP_BHATTACHARYYA) > 0.35] + [N]
FX, FY, FS = np.zeros(N), np.zeros(N), np.zeros(N)
for a, b in zip(shots, shots[1:]):
    ks = [k for k in range(a, b) if faces[k] is not None]
    if ks:
        med = lambda v: np.array([np.median(v[max(0, j - 6):j + 7]) for j in range(len(v))])
        ker = np.exp(-0.5 * (np.arange(-45, 46) / 22.0) ** 2); ker /= ker.sum()
        sm = lambda v: np.convolve(np.pad(v, 45, mode="edge"), ker, mode="same")[45:-45]
        FX[a:b] = sm(np.interp(np.arange(a, b), ks, med(np.array([(faces[k][0] + faces[k][2] / 2) * 2 for k in ks], np.float32))))
        FY[a:b] = sm(np.interp(np.arange(a, b), ks, med(np.array([(faces[k][1] + faces[k][3] / 2) * 2 for k in ks], np.float32))))
        FS[a:b] = float(np.median([faces[k][2] * 2 for k in ks]))
    else:
        FX[a:b], FY[a:b], FS[a:b] = SW / 2, CLEAN_H * 0.4, CLEAN_H / 4

def crop_to(src, k, tw, th, mode):
    fx, fy, fs = FX[k], FY[k], FS[k]
    asp = tw / th
    if mode == "full": ch = CLEAN_H
    elif mode == "close": ch = float(np.clip(fs * 3.4, 420, CLEAN_H))
    elif mode == "wide": ch = SW / asp
    else: ch = float(np.clip(fs * 3.0, 420, CLEAN_H))
    cw = ch * asp
    if cw > SW: cw = SW; ch = cw / asp
    ch = min(ch, CLEAN_H); cw = ch * asp
    x0 = float(np.clip(fx - cw / 2, 0, SW - cw)); y0 = float(np.clip(fy - ch * (0.40 if mode != "low" else 0.34), 0, CLEAN_H - ch))
    sc = tw / cw
    M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
    out = cv2.warpAffine(src, M, (tw, th), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    return out * 1.3 - cv2.GaussianBlur(out, (0, 0), 2.0) * 0.3

MODES = {0: [(61, "close")],
         1: [(0, "split"), (19, "close"), (31, "split"), (43, "full"), (54, "close"), (76, "split"), (95, "full"),
             (112, "close"), (121, "split"), (141, "close"), (146, "full"), (170, "split"), (192, "close"), (209, "full"), (214, "close")]}
MODE_T = sorted([(out_of(TW0(wi), ci) - 0.08 if wi else SPAN[ci][0], m) for ci, lst in MODES.items() for wi, m in lst])
def mode_at(tn):
    m = MODE_T[0][1]
    for t0, mm in MODE_T:
        if tn >= t0: m = mm
    return m
TOP_H = 608
_cache, _pos = {}, [0]
cap = cv2.VideoCapture(comb)
def src_frame(k):
    if k not in _cache:
        if len(_cache) > 40: _cache.clear()
        if _pos[0] != k: cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, f = cap.read(); _pos[0] = k + 1
        _cache[k] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else list(_cache.values())[-1]
    return _cache[k]
def render_view(k, mode):
    src = src_frame(k)
    if mode == "split":
        fr = np.zeros((H, W, 3), np.float32)
        fr[:TOP_H] = crop_to(src, k, W, TOP_H, "wide")
        fr[TOP_H:] = crop_to(src, k, W, H - TOP_H, "low")
        g = np.linspace(0, 1, 40)[:, None, None]
        fr[TOP_H - 20:TOP_H + 20] = fr[TOP_H - 20:TOP_H + 20] * (0.55 + 0.45 * np.abs(g * 2 - 1))
        return fr
    return crop_to(src, k, W, H, mode)

# ---------------------------------------------------------------- captions (sentence case, low)
F_CAP = ImageFont.truetype(INTER + "Inter-Medium.otf", 42)
CAPS = {0: [(61, 70, "Probably we can stop it from becoming a health checkup person"), (71, 75, "into a cardiac patient.")],
        1: [(0, 12, "So you used to very famously say that Indians are all high risk."), (13, 18, "There's nobody at low risk."),
            (19, 30, "So you're either at mildly high risk or at very high risk."),
            (31, 35, "So we, traditionally, genetically, phenotypically,"), (36, 42, "we belong to the high-risk population."),
            (43, 53, "Now, among that high risk, how high your risk is,"), (54, 60, "that we can pick up very early."),
            (61, 70, "Probably we can stop it from becoming a health checkup person"), (71, 75, "into a cardiac patient."),
            (76, 84, "It helps us to pick up those red flags"), (85, 94, "that we call something which can pick up very early,"),
            (95, 103, "to find out if, in future, this particular person"), (104, 111, "must come to me, say, for a health checkup,"),
            (112, 120, "and we have picked up, for example, visceral adiposity."), (121, 127, "For the patient, it is very common,"),
            (128, 140, "because for him it is a typical Indian subset that he belongs to."),
            (141, 145, "For him, visceral adiposity is no big deal."), (146, 158, "But we know now that this adiposity is going to build metabolic problems"),
            (159, 169, "in the future, and that will ultimately lead to cardiac issues."),
            (170, 179, "What this particular program does, in addition to it, is,"), (183, 191, "it suggests us if we can do something more."),
            (192, 200, "Right? If we missed out, say, a particular investigation,"), (201, 208, "such as hs-CRP or Lipoprotein(a),"),
            (209, 217, "or something which can further risk-stratify the patient"), (218, 224, "into a high risk or intermediate risk.")]}
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_CAP) > 820: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    img = Image.new("RGBA", (W, 56 * len(lines) + 40), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines): ds.text((W / 2, 20 + i * 56 + 3), ln, font=F_CAP, fill=230, anchor="ma")
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(6)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines): d.text((W / 2, 20 + i * 56), ln, font=F_CAP, fill=WHITE + (255,), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
caps = []
for ci, lst in CAPS.items():
    for i, (w0, w1, text) in enumerate(lst):
        s = out_of(TW0(w0), ci); e = out_of(TW1(w1), ci) + 0.3
        if i + 1 < len(lst):
            nx = out_of(TW0(lst[i + 1][0]), ci)
            if 0 < nx - e < 0.5: e = nx
        e = min(e, SPAN[ci][1] + 0.3)
        caps.append((s, e, cap_layer(text)))
CAP_Y = 1470

# ---------------------------------------------------------------- kinetic callouts (left, mid-height)
F_BIG = ImageFont.truetype(POP, 84); F_MID = ImageFont.truetype(POP, 60); F_NUM = ImageFont.truetype(POP, 30)
F_TAG = ImageFont.truetype(INTER + "Inter-SemiBold.otf", 24); F_SUB = ImageFont.truetype(INTER + "Inter-Regular.otf", 26)
CALLOUTS = [   # (clip, first word, last word, items)
    (0, 61, 75, [(61, "quote", "", CYAN), (61, "tag", "WE CAN STOP A", WHITE), (69, "mid", "HEALTH-CHECKUP PERSON", WHITE),
                 (72, "tag", "FROM BECOMING A", WHITE), (74, "big", "CARDIAC PATIENT.", CYAN)]),
    (1, 7, 12, [(7, "tag", "INDIANS ARE ALL", WHITE), (11, "big", "HIGH RISK.", CYAN)]),
    (1, 19, 30, [(19, "tag", "SO YOU'RE EITHER AT", WHITE), (23, "list", "MILDLY HIGH RISK", WHITE), (28, "list", "VERY HIGH RISK", WHITE)]),
    (1, 31, 42, [(31, "tag", "WE ARE", WHITE), (33, "mid", "TRADITIONALLY,", WHITE), (34, "mid", "GENETICALLY,", WHITE),
                 (35, "mid", "PHENOTYPICALLY", WHITE), (40, "big", "HIGH RISK.", CYAN)]),
    (1, 43, 60, [(43, "tag", "AMONG THE HIGH RISK", WHITE), (48, "big", "HOW HIGH?", WHITE), (56, "mid", "PICK IT UP", WHITE),
                 (59, "big", "VERY EARLY.", CYAN)]),
    (1, 76, 94, [(76, "tag", "IT HELPS US PICK UP", WHITE), (83, "big", "RED FLAGS", CYAN)]),
    (1, 112, 127, [(117, "tag", "FOR EXAMPLE", WHITE), (119, "big", "VISCERAL", WHITE), (120, "big", "ADIPOSITY", CYAN),
                   (126, "sub", "very common in Indians", WHITE)]),
    (1, 141, 169, [(141, "tag", "FOR HIM, IT IS", WHITE), (145, "big", "NO BIG DEAL", WHITE), (147, "strike", "", WHITE),
                   (156, "mid", "METABOLIC PROBLEMS", CYAN), (166, "tag", "LEADING TO", WHITE), (168, "big", "CARDIAC ISSUES.", CYAN)]),
    (1, 192, 208, [(197, "tag", "TESTS THAT GET MISSED", WHITE), (203, "list", "HS-CRP", WHITE), (207, "list", "LIPOPROTEIN(A)", WHITE)]),
    (1, 209, 224, [(213, "tag", "FURTHER", WHITE), (214, "big", "RISK-STRATIFY", CYAN), (220, "mid", "HIGH OR", WHITE),
                   (223, "mid", "INTERMEDIATE RISK.", WHITE)]),
]
CX, CY0 = 64, 960
def spaced(d, x, y, text, f, fill, track=4):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + track
    return x
def item_layer(kind, text, col, idx):
    if kind == "quote":
        img = Image.new("RGBA", (120, 110), (0, 0, 0, 0)); ImageDraw.Draw(img).text((0, -30), "“", font=ImageFont.truetype(POP, 150), fill=CYAN + (255,))
        return img, 92, 0
    f = {"tag": F_TAG, "big": F_BIG, "mid": F_MID, "list": F_MID, "sub": F_SUB}[kind]
    hgt = {"tag": 46, "big": 96, "mid": 72, "list": 78, "sub": 42}[kind]
    img = Image.new("RGBA", (W - CX, hgt + 20), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh); x = 0
    if kind == "list": ds.text((0, 28), f"{idx:02d}", font=F_NUM, fill=160); x = 70
    if kind == "tag":
        spaced(ds, 2, 4, text, f, 160); end = spaced(ImageDraw.Draw(Image.new("L", (1, 1))), 0, 0, text, f, 0)
    else:
        ds.text((x + 2, 4), text, font=f, fill=180); end = x + dd.textlength(text, font=f)
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(7)))
    img = Image.alpha_composite(img, s2); d_ = ImageDraw.Draw(img)
    if kind == "list": d_.text((0, 26), f"{idx:02d}", font=F_NUM, fill=CYAN + (255,))
    if kind == "tag": spaced(d_, 0, 0, text, f, (220, 228, 238, 255))
    elif kind == "sub": d_.text((x, 0), text, font=f, fill=(225, 232, 240, 255))
    else: d_.text((x, 0), text, font=f, fill=col + (255,))
    return img, hgt, end
class Callout:
    def __init__(self, ci, w0, w1, items):
        self.items = []; y = 0; li = 0; prev_big = None
        for wi, kind, text, col in items:
            t_ = out_of(TW0(wi), ci)
            if kind == "strike":
                self.items.append(dict(kind="strike", t=t_, y=prev_big[0], w=prev_big[1])); continue
            if kind == "list": li += 1
            img, hgt, wid = item_layer(kind, text, col, li)
            self.items.append(dict(kind=kind, t=t_, y=y, arr=np.asarray(img).astype(np.float32) / 255, w=wid))
            if kind in ("big", "mid"): prev_big = (y + hgt * 0.52, wid)
            y += hgt + (14 if kind == "quote" else 6)
        self.t0 = min(i["t"] for i in self.items) - 0.05
        self.t1 = min(out_of(TW1(w1), ci) + 0.9, SPAN[ci][1] + 0.2)
    def draw(self, fr, tn, nxt):
        end = min(self.t1, nxt - 0.05) if nxt else self.t1
        if not (self.t0 <= tn < end + 0.3): return
        out = 1 - ease((tn - end) / 0.3)
        for it in self.items:
            if tn < it["t"]: continue
            p = ease((tn - it["t"]) / 0.28)
            if it["kind"] == "strike":
                L = int(it["w"] * ease((tn - it["t"]) / 0.35)); y = CY0 + int(it["y"])
                fr[y - 4:y + 5, CX:CX + L] = fr[y - 4:y + 5, CX:CX + L] * (1 - out) + np.array(WHITE, np.float32) * out
                continue
            arr = it["arr"]; hh, ww = arr.shape[:2]
            y = CY0 + it["y"] + int(18 * (1 - p)); x = CX
            hv = min(hh, H - y); wv = min(ww, W - x)
            al = arr[:hv, :wv, 3:4] * p * out
            fr[y:y + hv, x:x + wv] = fr[y:y + hv, x:x + wv] * (1 - al) + arr[:hv, :wv, :3] * 255 * al
CALLS = sorted([Callout(*c) for c in CALLOUTS], key=lambda c: c.t0)

# ---------------------------------------------------------------- logo (top right) and end card
_lw = 175
def _ld(name):
    im = Image.open(os.path.join(REPO, "assets", name)).convert("RGBA")
    return np.asarray(im.resize((_lw, int(im.height * _lw / im.width)), Image.LANCZOS)).astype(np.float32) / 255
LOGO_DARKBG, LOGO_LIGHTBG = _ld("logo_on_dark.png"), _ld("logo_original.png")      # white wordmark / dark wordmark
# soft dark gradient behind the captions and callouts: the stage background here is bright white
_g = np.clip((np.arange(H, dtype=np.float32) - 760) / 560, 0, 1)
SCRIM = (0.68 * _g ** 1.3)[:, None, None]
LOGO_XY = (W - _lw - 56, 70)
def make_cta(text):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); f = ImageFont.truetype(INTER + "Inter-SemiBold.otf", 40); track = 6
    widths = [d.textlength(ch, font=f) for ch in text]; t_w = sum(widths) + track * (len(text) - 1)
    pw, ph, pad = int(t_w + 150), 110, 34
    img = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + pw, pad + ph + 8), ph // 2, fill=110)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14))); dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((pad, pad, pad + pw, pad + ph), ph // 2, fill=(255, 255, 255, 255))
    x = pad + (pw - t_w) / 2; asc, desc = f.getmetrics(); y = pad + (ph - (asc + desc)) / 2 + 2
    for ch, wd in zip(text, widths):
        dr.text((x, y), ch, font=f, fill=(34, 36, 40, 255)); x += wd + track
    return np.asarray(img).astype(np.float32) / 255
CTA = make_cta("LEARN MORE")

# ---------------------------------------------------------------- precap grade + heart monitor (same as Naman's video)
_vy, _vx = np.mgrid[0:H, 0:W].astype(np.float32)
TR_VIG = np.clip(1 - 0.85 * (((_vx - W / 2) / (W * 0.75)) ** 2 + ((_vy - H * 0.45) / (H * 0.62)) ** 2), 0.25, 1)[..., None]
_lut = 1 / (1 + np.exp(-9 * (np.linspace(0, 1, 256) - 0.48))); TR_LUT = (((_lut - _lut[0]) / (_lut[-1] - _lut[0])) * 0.92 + 0.02) * 255
def trailer_grade(fr, fi):
    y = fr[..., 0] * 0.299 + fr[..., 1] * 0.587 + fr[..., 2] * 0.114
    y = TR_LUT[np.clip(y, 0, 255).astype(np.uint8)] * 0.82
    g = np.stack([y * 0.97, y * 0.99, y * 1.03], -1) * TR_VIG
    g += cv2.resize(np.random.default_rng(fi).normal(0, 7, (H // 2, W // 2)).astype(np.float32), (W, H))[..., None]
    return g
ECG_Y = H // 2
GREEN, RED_ = np.array([70, 214, 120], np.float32), np.array([224, 42, 44], np.float32)
BEATS = [(170, 1.00), (470, 0.62), (740, 0.26)]
def pqrst(u):
    return (14 * np.exp(-((u + 52) / 11) ** 2) - 26 * np.exp(-((u + 9) / 4) ** 2) + 230 * np.exp(-(u / 5) ** 2)
            - 62 * np.exp(-((u - 10) / 5) ** 2) + 34 * np.exp(-((u - 62) / 17) ** 2))
XS_ = np.arange(0, W, dtype=np.float32); ECG_V = np.zeros_like(XS_)
for bx, amp in BEATS: ECG_V += amp * pqrst(XS_ - bx)
ECG_COL = np.array([GREEN * (1 - k) + RED_ * k for k in np.clip((XS_ - 260) / 380, 0, 1)], np.float32)
HEAD_END = 1.55
ECG_BG = (np.full((H, W, 3), 16, np.float32) + np.random.default_rng(3).normal(0, 2.2, (H, W, 1)).astype(np.float32)) * \
         (1 - 0.35 * (((_vx - W / 2) / W) ** 2 + ((_vy - H / 2) / H) ** 2) * 2)[..., None]
def ecg_frame(u):
    head = W * min(u / HEAD_END, 1.0); kf = ease((u - HEAD_END) / 0.3)
    pts = np.stack([XS_, ECG_Y - ECG_V * (1 - kf)], 1).astype(np.int32); n = int(head)
    lay = np.zeros((H, W, 3), np.float32)
    if n > 1:
        fade = np.clip(1 - (head - XS_[:n]) / W * 0.55, 0.35, 1)
        for i in range(1, n):
            c = tuple(float(v) for v in (ECG_COL[i] * (1 - kf) + RED_ * kf) * (fade[i] * (1 - kf) + kf))
            cv2.line(lay, tuple(pts[i - 1]), tuple(pts[i]), c, 5, cv2.LINE_AA)
        if u < HEAD_END: cv2.circle(lay, tuple(pts[n - 1]), 9, tuple(float(v) for v in np.minimum(ECG_COL[n - 1] * 1.4, 255)), -1, cv2.LINE_AA)
    return ECG_BG + cv2.GaussianBlur(lay, (0, 0), 12) * 1.6 + lay
def ecg_audio(sr=48000):
    n = int(ECG_DUR * sr); t_ = np.arange(n) / sr; y = np.zeros(n, np.float32)
    for bx, amp in BEATS:
        tb = HEAD_END * bx / W; m = (t_ >= tb) & (t_ < tb + 0.13)
        y += (np.sin(2 * np.pi * 1000 * t_) * np.sin(np.pi * np.clip((t_ - tb) / 0.13, 0, 1)) ** 0.5 * m * 0.22 * (0.5 + 0.5 * amp)).astype(np.float32)
    tf = HEAD_END * 860 / W
    flat = (t_ >= tf) * np.clip((t_ - tf) / 0.05, 0, 1) * (1 - np.clip((t_ - (ECG_DUR - 0.35)) / 0.35, 0, 1))
    return y + (np.sin(2 * np.pi * 1000 * t_) * flat * 0.20).astype(np.float32)
ecg_wav = os.path.join(TMP, "ecg.wav")
with wave.open(ecg_wav, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000); wf.writeframes((np.clip(ecg_audio(), -1, 1) * 32767).astype("<i2").tobytes())

# ---------------------------------------------------------------- audio
cutwav = os.path.join(TMP, "cut.wav")
fl = []
for i, (o0, o1, s, ci) in enumerate(timeline):
    last_of = i + 1 == len(timeline) or timeline[i + 1][3] != ci
    first_of = i == 0 or timeline[i - 1][3] != ci
    fo = 0.22 if last_of else 0.015
    fl.append(f"[0:a]atrim={s:.3f}:{s + o1 - o0:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={0.06 if first_of else 0.015},"
              f"afade=t=out:st={max(0, o1 - o0 - fo):.3f}:d={fo},adelay={int(round(o0 * 1000))}:all=1[a{i}];")
fl.append(f"[1:a]adelay={int(round(ECG_T0 * 1000))}:all=1[ecg];")
mix = "".join(fl) + "".join(f"[a{i}]" for i in range(len(timeline))) + f"[ecg]amix=inputs={len(timeline) + 1}:normalize=0,apad=whole_dur={TOTAL:.3f}[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", combp, "-i", ecg_wav, "-filter_complex", mix, "-map", "[a]", "-ar", "48000", "-t", f"{TOTAL:.3f}", cutwav], check=True)
_pre = ("highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2.5,highshelf=f=9000:g=1.5,"
        "deesser=i=0.35,acompressor=threshold=0.1:ratio=2.5:attack=8:release=150:makeup=1.5")
_m = subprocess.run(["ffmpeg", "-hide_banner", "-i", cutwav, "-af", _pre + ",loudnorm=I=-14:TP=-1:LRA=7:print_format=json", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
_j = json.loads(_m[_m.rindex("{"):_m.rindex("}") + 1])
VOICE = (_pre + f",loudnorm=I=-14:TP=-1:LRA=7:measured_I={_j['input_i']}:measured_TP={_j['input_tp']}:"
         f"measured_LRA={_j['input_lra']}:measured_thresh={_j['input_thresh']}:offset={_j['target_offset']}:linear=true")

# ---------------------------------------------------------------- render
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", cutwav, "-map", "0:v", "-map", "1:a", "-af", VOICE, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                        "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", OUT],
                       stdin=subprocess.PIPE)
def put(fr, L, x, y, a):
    hh, ww = L.shape[:2]; sub = fr[y:y + hh, x:x + ww]; al = L[..., 3:4] * a
    sub[:] = sub * (1 - al) + L[..., :3] * 255 * al
last = None
S1 = SPAN[1][0]
for fi in range(int(round(TOTAL * FPS))):
    tn = fi / FPS
    if tn < BODY:
        src, ci = src_of(tn)
        fr = render_view(min(int(round(src * FPS)), N - 1), mode_at(tn))
        if ci == 0: fr = trailer_grade(fr, fi)
        if ECG_T0 <= tn < S1 + ECG_X:                               # precap -> heart monitor -> answer, continuous
            u = tn - ECG_T0
            ecg = ecg_frame(min(u, ECG_DUR - 1 / FPS))
            if u < ECG_X: fr = fr * (1 - ease(u / ECG_X)) + ecg * ease(u / ECG_X)
            elif tn < S1: fr = ecg
            else: fr = ecg * (1 - ease((tn - S1) / ECG_X)) + fr * ease((tn - S1) / ECG_X)
            if tn < S1:
                enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes()); continue
        if tn < 0.4: fr = fr * ease(tn / 0.4)
        last = fr.copy()
        fr = fr * (1 - SCRIM)
        for c_i, c in enumerate(CALLS):
            c.draw(fr, tn, CALLS[c_i + 1].t0 if c_i + 1 < len(CALLS) else None)
        for s, e, L in caps:
            if s - 0.02 <= tn < e:
                a = ease((tn - s) / 0.15) * (1 - ease((tn - (e - 0.15)) / 0.15))
                hh = L.shape[0]; al = L[..., 3:4] * a
                fr[CAP_Y:CAP_Y + hh] = fr[CAP_Y:CAP_Y + hh] * (1 - al) + L[..., :3] * 255 * al
                break
        reg = fr[LOGO_XY[1]:LOGO_XY[1] + LOGO_DARKBG.shape[0], LOGO_XY[0]:LOGO_XY[0] + _lw]
        put(fr, LOGO_LIGHTBG if reg.mean() > 150 else LOGO_DARKBG, LOGO_XY[0], LOGO_XY[1], 1.0)
    else:
        u = tn - BODY
        blur = cv2.GaussianBlur(last, (0, 0), 26) * 0.55
        mb = ease(u / END_XF); fr = last * (1 - mb) + blur * mb
        ca = ease((u - 0.1) / 0.3)
        if ca > 0:
            y0, x0 = (H - CTA.shape[0]) // 2, (W - CTA.shape[1]) // 2
            put(fr, CTA, x0, y0, ca)
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", OUT)

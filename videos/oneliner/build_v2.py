"""Version 2, in the style of Naman's reference screen recording (videos/oneliner/reference_video.mp4):

- PRECAP: clip 2 first ("Cardiovascular disease still remains the leading cause of mortality in the world."),
  as a quote-style opening statement; then a 2 s heart-monitor insert (green beats turn red and go flat, with
  monitor beeps and the flatline tone); then clip 1, then clip 3, joined by soft crossfades
- framing changes on phrases like the reference: medium vertical shot, closer shot, and a split layout
  (the wide podcast shot on top, Naman below)
- small sentence captions low on screen + kinetic callouts on the left: a small letter-spaced tag,
  big bold capitals with one cyan accent, a strikethrough, numbered lists
- same edit as v1 (no "Okay", no repeated "that", no "Exactly. And"; unhurried pauses)
- ends on LEARN MORE for 1.7 s
"""
import json, os, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "biggest_pandemic_v2_9x16.mp4")
W, H, FPS = 1080, 1920, 25
POP = os.path.join(REPO, "assets", "fonts", "poppins-latin-800-normal.woff")
INTER = "/usr/share/fonts/opentype/inter/"
CYAN, WHITE = (52, 196, 240), (255, 255, 255)
def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

parts = [os.path.join(HERE, "raw", f"part{i}.mp4") for i in (1, 2, 3)]
lst = os.path.join(TMP, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
comb = os.path.join(TMP, "combined.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", comb], check=True)
words = json.load(open(os.path.join(HERE, "words.json")))
wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a16 = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
B1 = 28.52

# ---------------------------------------------------------------- edit: precap (clip 2), clip 1, clip 3
CLIPS = [(B1, 32.92), (0.42, 28.42), (34.27, 47.32)]
CUTS = [(2.30, 2.84)]
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
SIL = min(-30.0, float(np.percentile(rms[rms > -90], 90)) - 20.0)
ends = [wd[1] for wd in words if wd[2].strip().endswith((".", "?", "!"))]
s_ = None
for i, q in enumerate(np.append(rms < SIL, False)):
    if q and s_ is None: s_ = i
    if not q and s_ is not None:
        q0, q1 = s_ / 100, i / 100
        if q1 - q0 >= 0.55:
            k = 0.60 if any(e - 0.2 <= q0 <= e + 0.35 for e in ends) else 0.40
            if q1 - q0 > k: CUTS.append((q0 + k / 2, q1 - k / 2))
        s_ = None
GAP = {0: 0.25 + 2.0 + 0.35, 1: 0.45}         # precap -> 2 s heart-monitor flatline insert -> clip 1
timeline, t = [], 0.0
for ci, (c0, c1) in enumerate(CLIPS):
    if ci: t += GAP[ci - 1]
    t0 = c0
    for s, e in sorted(x for x in CUTS if c0 < x[0] < c1) + [(c1, c1)]:
        if s > t0 + 0.04: timeline.append((t, t + s - t0, t0, ci)); t += s - t0
        t0 = max(t0, e)
BODY = t
END_XF, CTA_HOLD = 0.4, 1.7                   # soft blur in, then LEARN MORE fully on screen for 1.7 s
TOTAL = BODY + END_XF + CTA_HOLD
CLIP_SPAN = {ci: ([x for x in timeline if x[3] == ci][0][0], [x for x in timeline if x[3] == ci][-1][1]) for ci in range(3)}
def src_of(tn):
    """output time -> source time (held at clip edges)"""
    best = None
    for o0, o1, s, ci in timeline:
        if o0 <= tn < o1: return s + tn - o0, ci
        if tn >= o1: best = (s + (o1 - o0) - 1 / FPS, ci)
    return best if best else (timeline[0][2], 0)
def first_src(ci): e = [x for x in timeline if x[3] == ci][0]; return e[2]
def out_of(src_t):
    for o0, o1, s, ci in timeline:
        if s - 0.02 <= src_t <= s + (o1 - o0) + 0.02: return o0 + min(max(src_t - s, 0), o1 - o0)
    cand = [(s - src_t, o0) for o0, o1, s, ci in timeline if s > src_t]
    return min(cand)[1] if cand else BODY
print(f"{len(timeline)} pieces, body {BODY:.1f}s")

# ---------------------------------------------------------------- face track (per camera shot, smoothed)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(comb); SW, SH = int(cap.get(3)), int(cap.get(4))
faces, hists = [], []
while True:
    ok, f = cap.read()
    if not ok: break
    small = cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA)
    hh = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256]); hists.append(cv2.normalize(hh, hh).flatten())
    d = fc.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(36, 36))
    faces.append(max(d, key=lambda b: b[2]) if len(d) else None)
N = len(hists)
shots = [0] + [k for k in range(1, N) if cv2.compareHist(hists[k - 1], hists[k], cv2.HISTCMP_BHATTACHARYYA) > 0.35] + [N]
FX, FY, FS = np.zeros(N), np.zeros(N), np.zeros(N)
for a, b in zip(shots, shots[1:]):
    ks = [k for k in range(a, b) if faces[k] is not None]
    if ks:
        med = lambda v: np.array([np.median(v[max(0, j - 6):j + 7]) for j in range(len(v))])
        ker = np.exp(-0.5 * (np.arange(-40, 41) / 20.0) ** 2); ker /= ker.sum()
        sm = lambda v: np.convolve(np.pad(v, 40, mode="edge"), ker, mode="same")[40:-40]
        for arr, fn in ((FX, lambda k: (faces[k][0] + faces[k][2] / 2) * 2), (FY, lambda k: (faces[k][1] + faces[k][3] / 2) * 2)):
            arr[a:b] = sm(np.interp(np.arange(a, b), ks, med(np.array([fn(k) for k in ks], np.float32))))
        FS[a:b] = float(np.median([faces[k][2] * 2 for k in ks]))
    else:
        FX[a:b], FY[a:b], FS[a:b] = SW / 2, SH * 0.4, SH / 3

def crop_to(src, k, tw, th, mode):
    """cut a tw x th view of source frame k: 'full' (medium, full height), 'close', or 'low' (split bottom)"""
    fx, fy, fs = FX[k], FY[k], FS[k]
    asp = tw / th
    if mode == "full": ch = SH
    elif mode == "close": ch = float(np.clip(fs * 2.8, 430, SH))
    else: ch = float(np.clip(fs * 2.3, 430, SH))
    cw = ch * asp
    if cw > SW: cw = SW; ch = cw / asp
    x0 = float(np.clip(fx - cw / 2, 0, SW - cw)); y0 = float(np.clip(fy - ch * (0.40 if mode != "low" else 0.34), 0, SH - ch))
    sc = tw / cw
    M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
    out = cv2.warpAffine(src, M, (tw, th), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    return out * 1.3 - cv2.GaussianBlur(out, (0, 0), 2.0) * 0.3

# layout per phrase (word index -> mode), like the reference's cutting between framings
MODES = [(73, "close"), (1, "split"), (15, "full"), (20, "close"), (32, "split"), (41, "full"), (58, "close"), (66, "split"),
         (87, "close"), (96, "full"), (102, "split"), (118, "close")]
MODE_T = sorted((out_of(words[wi][0]) - 0.08, m) for wi, m in MODES)
MODE_T[0] = (0.0, MODE_T[0][1])
def mode_at(tn):
    m = MODE_T[0][1]
    for t0, mm in MODE_T:
        if tn >= t0: m = mm
    return m
TOP_H = 608                                   # split: the wide 16:9 shot on top

def render_view(k, mode):
    src = src_frame_cached(k)
    if mode == "split":
        fr = np.zeros((H, W, 3), np.float32)
        fr[:TOP_H] = cv2.resize(src, (W, TOP_H), interpolation=cv2.INTER_AREA).astype(np.float32)
        fr[TOP_H:] = crop_to(src, k, W, H - TOP_H, "low")
        g = np.linspace(0, 1, 40)[:, None, None]                 # soft seam
        fr[TOP_H - 20:TOP_H + 20] = fr[TOP_H - 20:TOP_H + 20] * (0.55 + 0.45 * np.abs(g * 2 - 1))
        return fr
    return crop_to(src, k, W, H, mode)

# ---------------------------------------------------------------- small captions (sentence case, low)
F_CAP = ImageFont.truetype(INTER + "Inter-Medium.otf", 42)
CAPS = [(73, 76, "Cardiovascular disease still remains"), (77, 84, "the leading cause of mortality in the world."),
        (1, 8, "From a number of studies that we have done,"), (10, 19, "in the next decade or so, doctors will have two people."),
        (20, 25, "One would be 35 years old."), (26, 31, "The other would be 75 years old."),
        (32, 40, "Both with acute MI, which is the heart attack."), (41, 49, "The doctor, unfortunately, will have to save the 35-year-old"),
        (50, 57, "because he is packed. He doesn't have time."), (58, 65, "He'll have to let go the 75-year-old"),
        (66, 72, "if we don't solve this problem sooner."),
        (87, 91, "This is the biggest pandemic."), (92, 95, "It is not happening."), (96, 101, "There is no sudden heart attack."),
        (102, 109, "It's a build-up process of 10 years,"), (110, 117, "15 years, 5 years, based on your symptoms."),
        (118, 123, "And we really must catch that.")]
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_CAP) > 820: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    img = Image.new("RGBA", (W, 56 * len(lines) + 40), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines): ds.text((W / 2, 20 + i * 56 + 3), ln, font=F_CAP, fill=210, anchor="ma")
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(6)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines): d.text((W / 2, 20 + i * 56), ln, font=F_CAP, fill=WHITE + (255,), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
caps = []
for i, (w0, w1, text) in enumerate(CAPS):
    s = out_of(words[w0][0]); e = out_of(words[w1][1]) + 0.3
    if i + 1 < len(CAPS):
        nx = out_of(words[CAPS[i + 1][0]][0])
        if 0 < nx - e < 0.5: e = nx
    caps.append((s, e, cap_layer(text)))
CAP_Y = 1470

# ---------------------------------------------------------------- kinetic callouts (left, mid-height)
F_BIG = ImageFont.truetype(POP, 88); F_MID = ImageFont.truetype(POP, 64); F_NUM = ImageFont.truetype(POP, 30)
F_TAG = ImageFont.truetype(INTER + "Inter-SemiBold.otf", 24); F_SUB = ImageFont.truetype(INTER + "Inter-Regular.otf", 26)
# items: (word, kind, text, colour) kinds: quote, tag, big, mid, strike (strikes the previous big), list (numbered), sub
CALLOUTS = [
    (73, 84 + 0, [(73, "quote", "", CYAN), (73, "tag", "CARDIOVASCULAR DISEASE", WHITE), (75, "big", "STILL THE", WHITE),
                  (77, "big", "LEADING CAUSE", CYAN), (80, "big", "OF MORTALITY.", WHITE)]),
    (15, 31, [(15, "tag", "IN THE NEXT DECADE, DOCTORS WILL HAVE", WHITE), (18, "big", "TWO PEOPLE", CYAN),
              (23, "list", "35 YEARS OLD", WHITE), (29, "list", "75 YEARS OLD", WHITE)]),
    (32, 40, [(32, "tag", "BOTH WITH", WHITE), (34, "big", "ACUTE MI", WHITE), (36, "tag", "WHICH IS THE", WHITE),
              (38, "big", "HEART ATTACK", CYAN)]),
    (43, 57, [(43, "tag", "THE DOCTOR WILL HAVE TO", WHITE), (46, "big", "SAVE", CYAN), (47, "mid", "THE 35-YEAR-OLD", WHITE)]),
    (58, 65, [(58, "tag", "AND", WHITE), (61, "big", "LET GO", CYAN), (63, "mid", "THE 75-YEAR-OLD", WHITE)]),
    (66, 72, [(66, "tag", "IF WE DON'T SOLVE THIS PROBLEM", WHITE), (72, "big", "SOONER.", CYAN)]),
    (87, 91, [(87, "tag", "THIS IS", WHITE), (89, "big", "THE BIGGEST", WHITE), (91, "big", "PANDEMIC.", CYAN)]),
    (96, 101, [(96, "tag", "THERE IS NO", WHITE), (99, "big", "SUDDEN", WHITE), (100, "strike", "", WHITE), (100, "big", "HEART ATTACK", CYAN)]),
    (102, 117, [(102, "tag", "A BUILD-UP PROCESS OF", WHITE), (108, "list", "10 YEARS", WHITE), (110, "list", "15 YEARS", WHITE),
                (112, "list", "5 YEARS", WHITE), (114, "sub", "based on your symptoms", WHITE)]),
    (118, 123, [(120, "tag", "WE REALLY MUST", WHITE), (122, "big", "CATCH THAT.", CYAN)]),
]
CX, CY0 = 64, 960                                   # callout block: left, from this y downward

def spaced(d, x, y, text, f, fill, track=4):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + track
    return x

def item_layer(kind, text, col, idx):
    """returns (rgba array, height, width of text for strike)"""
    if kind == "quote":
        img = Image.new("RGBA", (120, 110), (0, 0, 0, 0)); ImageDraw.Draw(img).text((0, -30), "“", font=ImageFont.truetype(POP, 150), fill=CYAN + (255,))
        return img, 92, 0
    f = {"tag": F_TAG, "big": F_BIG, "mid": F_MID, "list": F_MID, "sub": F_SUB}[kind]
    hgt = {"tag": 46, "big": 100, "mid": 76, "list": 80, "sub": 42}[kind]
    img = Image.new("RGBA", (W - CX, hgt + 20), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh); d_ = ImageDraw.Draw(img)
    x = 0
    if kind == "list":
        num = f"{idx:02d}"
        ds.text((0, 30), num, font=F_NUM, fill=160); x = 70
    if kind == "tag":
        spaced(ds, 2, 4, text, f, 160); end = spaced(ImageDraw.Draw(Image.new("L", (1, 1))), 0, 0, text, f, 0)
    else:
        ds.text((x + 2, 4), text, font=f, fill=180); end = x + ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f)
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(7)))
    img = Image.alpha_composite(img, s2); d_ = ImageDraw.Draw(img)
    if kind == "list": d_.text((0, 28), f"{idx:02d}", font=F_NUM, fill=CYAN + (255,))
    if kind == "tag": spaced(d_, 0, 0, text, f, (220, 228, 238, 255))
    elif kind == "sub": d_.text((x, 0), text, font=f, fill=(225, 232, 240, 255))
    else: d_.text((x, 0), text, font=f, fill=col + (255,))
    return img, hgt, end

class Callout:
    def __init__(self, w0, w1, items):
        self.items = []; y = 0; li = 0; prev_big = None
        for wi, kind, text, col in items:
            t_ = out_of(words[wi][0])
            if kind == "strike":
                self.items.append(dict(kind="strike", t=t_, y=prev_big[0], w=prev_big[1])); continue
            if kind == "list": li += 1
            img, hgt, wid = item_layer(kind, text, col, li)
            arr = np.asarray(img).astype(np.float32) / 255
            self.items.append(dict(kind=kind, t=t_, y=y, arr=arr, w=wid))
            if kind in ("big", "mid"): prev_big = (y + hgt * 0.52, wid)
            y += hgt + (14 if kind == "quote" else 6)
        self.t0 = min(i["t"] for i in self.items) - 0.05
        self.t1 = out_of(words[w1][1]) + 0.9
    def draw(self, fr, tn, nxt):
        end = min(self.t1, nxt - 0.05) if nxt else self.t1
        if not (self.t0 <= tn < end + 0.3): return
        out = 1 - ease((tn - end) / 0.3)
        for it in self.items:
            if tn < it["t"]: continue
            p = ease((tn - it["t"]) / 0.28)
            if it["kind"] == "strike":
                L = int(it["w"] * ease((tn - it["t"]) / 0.35))
                y = CY0 + int(it["y"])
                fr[y - 4:y + 5, CX:CX + L] = fr[y - 4:y + 5, CX:CX + L] * (1 - out) + np.array(WHITE, np.float32) * out
                continue
            arr = it["arr"]; hh, ww = arr.shape[:2]
            y = CY0 + it["y"] + int(18 * (1 - p)); x = CX
            hv = min(hh, H - y); wv = min(ww, W - x)
            al = arr[:hv, :wv, 3:4] * p * out
            fr[y:y + hv, x:x + wv] = fr[y:y + hv, x:x + wv] * (1 - al) + arr[:hv, :wv, :3] * 255 * al
CALLS = [Callout(w0, w1, items) for w0, w1, items in CALLOUTS]
CALLS.sort(key=lambda c: c.t0)

# ---------------------------------------------------------------- end card
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

# ---------------------------------------------------------------- audio (same edit; clips fade softly at their edges)
# ---------------------------------------------------------------- 2 s heart-monitor insert: green beats turn red and go flat
ECG_T0 = CLIP_SPAN[0][1] + 0.25                 # starts just after "...in the world."
ECG_DUR = 2.0
ECG_Y = H // 2
GREEN, RED_ = np.array([70, 214, 120], np.float32), np.array([224, 42, 44], np.float32)
BEATS = [(170, 1.00), (470, 0.62), (740, 0.26)]  # x of each beat, amplitude (fading)
def pqrst(u):
    """one heartbeat shape, u in px from beat centre; returns upward displacement in px (amplitude 1)"""
    return (14 * np.exp(-((u + 52) / 11) ** 2) - 26 * np.exp(-((u + 9) / 4) ** 2) + 230 * np.exp(-(u / 5) ** 2)
            - 62 * np.exp(-((u - 10) / 5) ** 2) + 34 * np.exp(-((u - 62) / 17) ** 2))
XS_ = np.arange(0, W, dtype=np.float32)
ECG_V = np.zeros_like(XS_)
for bx, amp in BEATS: ECG_V += amp * pqrst(XS_ - bx)
ECG_COL = np.array([GREEN * (1 - k) + RED_ * k for k in np.clip((XS_ - 260) / 380, 0, 1)], np.float32)
HEAD_END = 1.55                                   # the trace reaches the right edge here, then rests as a flat red line
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
ECG_BG = (np.full((H, W, 3), 16, np.float32) + np.random.default_rng(3).normal(0, 2.2, (H, W, 1)).astype(np.float32)) * \
         (1 - 0.35 * (((_xx - W / 2) / W) ** 2 + ((_yy - H / 2) / H) ** 2) * 2)[..., None]
def ecg_frame(u):
    head = W * min(u / HEAD_END, 1.0)
    img = np.zeros((H, W), np.float32); col = np.zeros((H, W, 3), np.float32)
    pts = np.stack([XS_, ECG_Y - ECG_V], 1).astype(np.int32)
    n = int(head)
    lay = np.zeros((H, W, 3), np.float32)
    if n > 1:
        age = (head - XS_[:n]) / W                               # older trace dims a little, like a monitor
        fade = np.clip(1 - age * 0.55, 0.35, 1)
        for i in range(1, n):
            c = tuple(float(v) for v in ECG_COL[i] * fade[i])
            cv2.line(lay, tuple(pts[i - 1]), tuple(pts[i]), c, 5, cv2.LINE_AA)
        if u < HEAD_END:                                           # bright head
            cv2.circle(lay, tuple(pts[n - 1]), 9, tuple(float(v) for v in np.minimum(ECG_COL[n - 1] * 1.4, 255)), -1, cv2.LINE_AA)
    glow = cv2.GaussianBlur(lay, (0, 0), 12) * 1.6
    fr = ECG_BG + glow + lay
    fr *= ease(u / 0.25) * (1 - ease((u - (ECG_DUR - 0.25)) / 0.25))
    return fr

# monitor sound: a beep on each beat (fading), then the flatline tone
def ecg_audio(sr=48000):
    n = int(ECG_DUR * sr); t_ = np.arange(n) / sr; y = np.zeros(n, np.float32)
    for bx, amp in BEATS:
        tb = HEAD_END * bx / W; m = (t_ >= tb) & (t_ < tb + 0.13)
        env = np.sin(np.pi * np.clip((t_ - tb) / 0.13, 0, 1)) ** 0.5
        y += (np.sin(2 * np.pi * 1000 * t_) * env * m * 0.22 * (0.5 + 0.5 * amp)).astype(np.float32)
    tf = HEAD_END * 860 / W
    flat = (t_ >= tf) * np.clip((t_ - tf) / 0.05, 0, 1) * (1 - np.clip((t_ - (ECG_DUR - 0.35)) / 0.35, 0, 1))
    y += (np.sin(2 * np.pi * 1000 * t_) * flat * 0.20).astype(np.float32)
    return y
ecg_wav = os.path.join(TMP, "ecg.wav")
with wave.open(ecg_wav, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
    wf.writeframes((np.clip(ecg_audio(), -1, 1) * 32767).astype("<i2").tobytes())

cutwav = os.path.join(TMP, "cut_v2.wav")
fl = []
for i, (o0, o1, s, ci) in enumerate(timeline):
    last_of = i + 1 == len(timeline) or timeline[i + 1][3] != ci
    first_of = i == 0 or timeline[i - 1][3] != ci
    fo = 0.22 if last_of else 0.015
    fl.append(f"[0:a]atrim={s:.3f}:{s + o1 - o0:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={0.06 if first_of else 0.015},"
              f"afade=t=out:st={max(0, o1 - o0 - fo):.3f}:d={fo},adelay={int(round(o0 * 1000))}:all=1[a{i}];")
fl.append(f"[1:a]adelay={int(round(ECG_T0 * 1000))}:all=1[ecg];")
mix = "".join(fl) + "".join(f"[a{i}]" for i in range(len(timeline))) + f"[ecg]amix=inputs={len(timeline) + 1}:normalize=0,apad=whole_dur={TOTAL:.3f}[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-i", ecg_wav, "-filter_complex", mix, "-map", "[a]", "-ar", "48000", "-t", f"{TOTAL:.3f}", cutwav], check=True)
VOICE = ("highpass=f=70,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2,highshelf=f=9000:g=1.5,"
         "deesser=i=0.3,acompressor=threshold=0.1:ratio=2.2:attack=8:release=160:makeup=1.4,loudnorm=I=-14:TP=-1:LRA=7")

# ---------------------------------------------------------------- source frames: random access with a small cache
cap = cv2.VideoCapture(comb)
_cache, _pos = {}, [0]
def src_frame_cached(k):
    if k not in _cache:
        if len(_cache) > 40: _cache.clear()
        if _pos[0] != k: cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, f = cap.read(); _pos[0] = k + 1
        _cache[k] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else list(_cache.values())[-1]
    return _cache[k]

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", cutwav, "-map", "0:v", "-map", "1:a", "-af", VOICE, "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                        "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", OUT],
                       stdin=subprocess.PIPE)
XF = 0.6                                           # crossfade between clips
def view_at(tn):
    src, ci = src_of(min(tn, BODY - 1 / FPS))
    return render_view(min(int(round(src * FPS)), N - 1), mode_at(tn)), ci
last = None
for fi in range(int(round(TOTAL * FPS))):
    tn = fi / FPS
    if tn < BODY:
        fr, ci = view_at(tn)
        # crossfade into the next clip: during the gap before clip ci+1 starts, blend the held frame with its first frame
        if ECG_T0 - 0.25 <= tn < CLIP_SPAN[1][0]:                  # precap -> heart monitor -> clip 1
            u = tn - ECG_T0
            if u < 0:
                fr = fr * (1 - ease((tn - (ECG_T0 - 0.25)) / 0.25))
            elif u < ECG_DUR:
                fr = ecg_frame(u)
            else:
                k2 = min(int(round(first_src(1) * FPS)), N - 1)
                fr = render_view(k2, mode_at(CLIP_SPAN[1][0] + 0.01)) * ease((tn - (ECG_T0 + ECG_DUR)) / (CLIP_SPAN[1][0] - ECG_T0 - ECG_DUR))
            enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes()); continue
        for nc in (2,):
            s0 = CLIP_SPAN[nc][0]
            if s0 - XF <= tn < s0 and ci == nc - 1:
                k2 = min(int(round(first_src(nc) * FPS)), N - 1)
                m = ease((tn - (s0 - XF)) / XF)
                fr = fr * (1 - m) + render_view(k2, mode_at(s0 + 0.01)) * m
        if tn < 0.5: fr = fr * ease(tn / 0.5)
        last = fr.copy()
        for c_i, c in enumerate(CALLS):
            c.draw(fr, tn, CALLS[c_i + 1].t0 if c_i + 1 < len(CALLS) else None)
        for s, e, L in caps:
            if s - 0.02 <= tn < e:
                a = ease((tn - s) / 0.15) * (1 - ease((tn - (e - 0.15)) / 0.15))
                hh = L.shape[0]; al = L[..., 3:4] * a
                fr[CAP_Y:CAP_Y + hh] = fr[CAP_Y:CAP_Y + hh] * (1 - al) + L[..., :3] * 255 * al
                break
    else:
        u = tn - BODY
        blur = cv2.GaussianBlur(last, (0, 0), 26) * 0.55
        mb = ease(u / END_XF); fr = last * (1 - mb) + blur * mb
        ca = ease((u - 0.1) / 0.3)
        if ca > 0:
            y0, x0 = (H - CTA.shape[0]) // 2, (W - CTA.shape[1]) // 2
            al = CTA[..., 3:4] * ca
            fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] = fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] * (1 - al) + CTA[..., :3] * 255 * al
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", OUT)

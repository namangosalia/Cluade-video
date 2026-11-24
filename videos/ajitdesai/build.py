"""Dr Ajit Desai (Jaslok) -> vertical short in the style of Naman's reference screenshot ("one life."):
tight close-up on the face, short bold lowercase phrases at chin level, nothing else on screen.

- clip 1 is the trailer: dark cinematic black & white, "50% of heart attacks since 2020 ... below the age of 40"
- it crossfades (no black) into clips 2 and 3, in colour
- credentials card when clip 2 starts: Dr Ajit Desai / Additional Director of Cardiology /
  Jaslok Hospital & Research Centre, Mumbai
- long pauses shortened to a natural breath, filler "called" removed; ends on LEARN MORE
"""
import json, os, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "ajit_desai_educational_9x16.mp4")
W, H, FPS = 1080, 1920, 30
POP = os.path.join(REPO, "assets", "fonts", "poppins-latin-800-normal.woff")
INTER = "/usr/share/fonts/opentype/inter/"
def F(n, s): return ImageFont.truetype(INTER + n, s)
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
B1, B2 = 7.19, 7.19 + 36.50

# ---------------------------------------------------------------- edit
CLIPS = [(0.0, 7.12), (7.15, B2 - 0.05), (B2, words[-1][1] + 0.35)]
CUTS = [(24.18, 25.45)]                               # "...advise them, called (pause)" -> "advise them. The process..."
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
SIL = -37.0                                            # quiet hall: pauses sit at about -40 dB, speech -26 to -34
ends = [wd[1] for wd in words if wd[2].strip().endswith((".", "?", "!", ","))]
s_ = None
for i, q in enumerate(np.append(rms < SIL, False)):
    if q and s_ is None: s_ = i
    if not q and s_ is not None:
        q0, q1 = s_ / 100, i / 100
        if q1 - q0 >= 0.18:                                   # smooth: every hesitation gap trimmed to a breath
            k = 0.26 if any(e - 0.2 <= q0 <= e + 0.35 for e in ends) else 0.14
            if q1 - q0 > k: CUTS.append((q0 + k / 2, q1 - k / 2))
        s_ = None
XF = 0.7                                              # crossfade between clips (overlapping, no black)
timeline, t = [], 0.0
for ci, (c0, c1) in enumerate(CLIPS):
    if ci == 1: t += 0.35                             # a breath after the trailer line
    t0 = c0
    for s, e in sorted(x for x in CUTS if c0 < x[0] < c1) + [(c1, c1)]:
        if s > t0 + 0.04: timeline.append((t, t + s - t0, t0, ci)); t += s - t0
        t0 = max(t0, e)
BODY = t
END_XF, CTA_HOLD = 0.4, 1.8
TOTAL = BODY + END_XF + CTA_HOLD
SPAN = {ci: ([x for x in timeline if x[3] == ci][0][0], [x for x in timeline if x[3] == ci][-1][1]) for ci in range(3)}
def srcs_at(tn):
    """all (source time, clip) active at tn (two during an overlap)"""
    out = []
    for ci in range(3):
        a_, b_ = SPAN[ci]
        if a_ - XF <= tn < b_ + XF:
            pcs = [x for x in timeline if x[3] == ci]
            tt = min(max(tn, a_), b_ - 1 / FPS)
            for o0, o1, s, c in pcs:
                if o0 <= tt < o1: out.append((s + tt - o0, ci)); break
            else: out.append((pcs[-1][2] + pcs[-1][1] - pcs[-1][0] - 1 / FPS, ci))
    return out
def weight(tn, ci):
    a_, b_ = SPAN[ci]
    wi = 1.0 if ci == 0 else ease((tn - (a_ - XF * 0.5)) / XF)
    wo = 1.0 if ci == 2 else 1 - ease((tn - (b_ - XF * 0.5)) / XF)
    return wi * wo
def out_of(src_t, clip):
    for o0, o1, s, ci in timeline:
        if ci == clip and s - 0.02 <= src_t <= s + (o1 - o0) + 0.02: return o0 + min(max(src_t - s, 0), o1 - o0)
    cand = [(s - src_t, o0) for o0, o1, s, ci in timeline if ci == clip and s > src_t]
    return min(cand)[1] if cand else SPAN[clip][1]
print(f"{len(timeline)} pieces, body {BODY:.1f}s")

# ---------------------------------------------------------------- close-up framing (face tracked, smoothed)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(comb); SW, SH = int(cap.get(3)), int(cap.get(4)); N = int(cap.get(7))
fx, fy, fs = [], [], []
for k in range(N):
    ok, f = cap.read()
    if not ok: break
    if k % 3: continue
    d = fc.detectMultiScale(cv2.cvtColor(cv2.resize(f, (SW // 2, SH // 2)), cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(30, 30))
    if len(d):
        b = max(d, key=lambda b: b[2]); fx.append((k, (b[0] + b[2] / 2) * 2)); fy.append((k, (b[1] + b[3] / 2) * 2)); fs.append(b[2] * 2)
ks = [k for k, _ in fx]
ker = np.exp(-0.5 * (np.arange(-60, 61) / 25.0) ** 2); ker /= ker.sum()
sm = lambda v: np.convolve(np.pad(v, 60, mode="edge"), ker, mode="same")[60:-60]
FX = sm(np.interp(np.arange(N), ks, [v for _, v in fx])); FY = sm(np.interp(np.arange(N), ks, [v for _, v in fy]))
FS = float(np.median(fs))
CH = float(np.clip(FS * 3.2, 420, SH)); CW = CH * 9 / 16       # tight, like the reference
cap = cv2.VideoCapture(comb); _pos = [0]; _cur = [None]
def frame_at(k):
    if _pos[0] != k: cap.set(cv2.CAP_PROP_POS_FRAMES, k)
    ok, f = cap.read(); _pos[0] = k + 1
    if ok: _cur[0] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
    return _cur[0]
def closeup(k, z=1.0):
    ch = CH / z; cw = ch * 9 / 16
    x0 = float(np.clip(FX[k] - cw / 2, 0, SW - cw)); y0 = float(np.clip(FY[k] - ch * 0.36, 0, SH - ch))
    sc = W / cw
    M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
    o = cv2.warpAffine(frame_at(k), M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    return o * 1.3 - cv2.GaussianBlur(o, (0, 0), 2.0) * 0.3

# ---------------------------------------------------------------- trailer grade (clip 1)
_vy, _vx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = np.clip(1 - 0.85 * (((_vx - W / 2) / (W * 0.75)) ** 2 + ((_vy - H * 0.42) / (H * 0.62)) ** 2), 0.25, 1)[..., None]
_l = 1 / (1 + np.exp(-9 * (np.linspace(0, 1, 256) - 0.5))); LUT = (((_l - _l[0]) / (_l[-1] - _l[0])) * 0.92 + 0.02) * 255
def bw(fr, fi):
    y = fr[..., 0] * 0.299 + fr[..., 1] * 0.587 + fr[..., 2] * 0.114
    y = LUT[np.clip(y, 0, 255).astype(np.uint8)] * 0.80
    g = np.stack([y * 0.97, y * 0.99, y * 1.03], -1) * VIG
    return g + cv2.resize(np.random.default_rng(fi).normal(0, 7, (H // 2, W // 2)).astype(np.float32), (W, H))[..., None]

# ---------------------------------------------------------------- captions: short bold lowercase phrases at chin level
CHUNKS = [(0, 0, 0, "unfortunately,"), (0, 1, 2, "50%"), (0, 3, 6, "of heart attacks"), (0, 7, 8, "since 2020"),
          (0, 9, 10, "are occurring"), (0, 11, 13, "below the age"), (0, 14, 16, "of 40 years."),
          (1, 17, 22, "what we are trying to do"), (1, 23, 23, "with jaslok hospital"), (1, 23, 23, "along with anginax"),
          (1, 24, 26, "is to screen"), (1, 27, 28, "the patients"), (1, 29, 33, "who are at higher risk,"),
          (1, 34, 36, "moderate risk"), (1, 37, 39, "or lower risk,"), (1, 40, 45, "as far as their cardiac profile"),
          (1, 46, 47, "is concerned."), (1, 48, 52, "and then I advise them."), (1, 54, 55, "the process"),
          (1, 56, 58, "is extremely simple."), (1, 59, 64, "it won't take more than"), (1, 65, 67, "about 2 minutes"),
          (1, 68, 70, "to assess them."), (1, 71, 74, "particularly if they have"), (1, 75, 77, "their previous investigations"),
          (1, 78, 80, "with them, ready."), (1, 81, 85, "certain investigations,"), (1, 86, 91, "not a whole battery of them."),
          (1, 92, 96, "the investigation is basically"), (1, 97, 100, "related to the cardiac profile."),
          (2, 101, 106, "we will be able to identify"), (2, 107, 108, "these patients"), (2, 109, 119, "who are going to be at high risk"),
          (2, 120, 122, "or moderate risk,"), (2, 123, 128, "and accordingly advise them"), (2, 129, 130, "with medications"),
          (2, 131, 134, "or further investigation"), (2, 135, 139, "to take care of themselves.")]
# the AnginaX line: split "with jaslok hospital" / "along with anginax" across the stretch 8.3-11.6 s
F_CAP = ImageFont.truetype(POP, 82)
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_CAP) > 900: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    img = Image.new("RGBA", (W, 100 * len(lines) + 60), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines): ds.text((W / 2, 30 + i * 100 + 4), ln, font=F_CAP, fill=160, anchor="ma")
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(10)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines): d.text((W / 2, 30 + i * 100), ln, font=F_CAP, fill=(255, 255, 255, 255), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
special = {"with jaslok hospital": (8.55, 10.15), "along with anginax": (10.15, 11.70)}
caps = []
for i, (ci, w0, w1, text) in enumerate(CHUNKS):
    if text in special: s0, e0 = special[text]
    else: s0, e0 = words[w0][0], words[w1][1]
    s = out_of(s0, ci); e = out_of(e0, ci) + 0.3
    if i + 1 < len(CHUNKS):
        n_ci, n0, _, n_t = CHUNKS[i + 1]
        nx = out_of(special[n_t][0] if n_t in special else words[n0][0], n_ci)
        if 0 < nx - e < 0.45 or nx < e: e = nx
    caps.append((s, e, cap_layer(text)))
CAP_CY = int(H * 0.60)

# ---------------------------------------------------------------- credentials card (when clip 2 starts)
def cred():
    f1, f2, f3 = F("Inter-Bold.otf", 54), F("Inter-SemiBold.otf", 33), F("Inter-Regular.otf", 29)
    t1, t2, t3 = "Dr Ajit Desai", "Additional Director of Cardiology", "Jaslok Hospital & Research Centre, Mumbai"
    wv = int(max(dd.textlength(t1, font=f1), dd.textlength(t2, font=f2), dd.textlength(t3, font=f3))) + 64
    pad = 24; hh = 196
    img = Image.new("RGBA", (wv + 2 * pad, hh + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + wv, pad + hh + 8), 20, fill=140)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad, pad, pad + wv, pad + hh), 20, fill=(10, 16, 28, 215))
    d.rectangle((pad, pad + 16, pad + 6, pad + hh - 16), fill=(52, 196, 240, 255))
    d.text((pad + 30, pad + 18), t1, font=f1, fill=(255, 255, 255, 255))
    d.text((pad + 30, pad + 90), t2, font=f2, fill=(255, 205, 96, 255))
    d.text((pad + 30, pad + 140), t3, font=f3, fill=(214, 224, 238, 255))
    return np.asarray(img).astype(np.float32) / 255
CRED = cred()
CRED_T = (SPAN[1][0] + 0.3, SPAN[1][0] + 6.5)
CRED_XY = (W - CRED.shape[1] - 6, 760)              # right side, beside his shoulder

def make_cta(text):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); f = F("Inter-SemiBold.otf", 32); track = 4
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
CTA = make_cta("FIND OUT ABOUT YOUR HEARTPASS")

# ---------------------------------------------------------------- educational callouts (below the captions)
POPB = ImageFont.truetype(POP, 76); POPM = ImageFont.truetype(POP, 46); TAGF = F("Inter-SemiBold.otf", 26)
CYAN, BLUE_ = (52, 196, 240), (70, 150, 255)
def tw_(t, f): return dd.textlength(t, font=f)
def text_block(tag, big, col):
    wv = int(max(tw_(big, POPB), sum(tw_(c, TAGF) + 5 for c in tag))) + 40
    img = Image.new("RGBA", (wv, 150), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    x = 22
    for c in tag: ds.text((x, 8), c, font=TAGF, fill=170); x += tw_(c, TAGF) + 5
    ds.text((22, 44), big, font=POPB, fill=190)
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(8)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img); x = 20
    for c in tag: d.text((x, 6), c, font=TAGF, fill=(228, 234, 242, 255)); x += tw_(c, TAGF) + 5
    d.text((20, 40), big, font=POPB, fill=col + (255,))
    return np.asarray(img).astype(np.float32) / 255
def chip(label, col, w_=300, h_=120, fill_a=225, icon=None):
    pad = 18
    img = Image.new("RGBA", (w_ + 2 * pad, h_ + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + w_, pad + h_ + 8), 24, fill=150)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(12))); d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad, pad, pad + w_, pad + h_), 24, fill=(12, 18, 30, fill_a), outline=col + (255,), width=4)
    f = POPM if tw_(label, POPM) < w_ - 40 else ImageFont.truetype(POP, 34)
    d.text((pad + w_ / 2 + (18 if icon else 0), pad + h_ / 2), label, font=f, fill=col + (255,), anchor="mm")
    if icon == "check":
        cx = pad + w_ / 2 - tw_(label, f) / 2 - 22; cy = pad + h_ / 2
        d.line((cx - 16, cy, cx - 5, cy + 12, cx + 14, cy - 14), fill=col + (255,), width=7)
    return np.asarray(img).astype(np.float32) / 255
RED_, AMB_, GRN_ = (236, 78, 74), (242, 184, 60), (88, 206, 120)
T = lambda i, c: out_of(words[i][0], c)
TE = lambda i, c: out_of(words[i][1], c)
EDU = []     # (t_in, t_out, [(t_appear, layer, x, y)])
def add(t_in, t_out, items): EDU.append((t_in, t_out, items))
Y0 = 1330
b = text_block("ANGINAX HELPS DOCTORS", "SCREEN", CYAN); add(T(26, 1), T(29, 1), [(T(26, 1), b, (W - b.shape[1]) // 2, Y0)])
cards = [chip("HIGH", RED_, 280), chip("MODERATE", AMB_, 280), chip("LOW", GRN_, 280)]
cx3 = [(W - 3 * cards[0].shape[1] + 2 * 12) // 2 + i * (cards[0].shape[1] - 12) for i in range(3)]
add(T(32, 1) - 0.1, TE(47, 1), [(T(32, 1), cards[0], cx3[0], Y0), (T(35, 1), cards[1], cx3[1], Y0), (T(38, 1), cards[2], cx3[2], Y0)])
b = text_block("TAKES ONLY ABOUT", "2 MINUTES", CYAN); add(T(59, 1), TE(70, 1), [(T(66, 1) - 0.2, b, (W - b.shape[1]) // 2, Y0)])
add(T(117, 2) - 0.1, TE(124, 2), [(T(118, 2), cards[0], cx3[0], Y0), (T(121, 2), cards[1], cx3[1], Y0)])
m1, m2 = chip("MEDICATION", CYAN, 420, 110), chip("FURTHER INVESTIGATION", CYAN, 520, 110)
add(T(129, 2) - 0.1, TE(134, 2) + 0.2, [(T(129, 2), m1, (W - m1.shape[1]) // 2, Y0), (T(132, 2), m2, (W - m2.shape[1]) // 2, Y0 + 140)])
tc = chip("TAKE CARE", BLUE_, 480, 120, icon="check")
add(T(135, 2) - 0.05, SPAN[2][1] + 0.3, [(T(136, 2), tc, (W - tc.shape[1]) // 2, Y0)])
def draw_edu(fr, tn):
    for t_in, t_out, items in EDU:
        if not (t_in <= tn < t_out + 0.3): continue
        o = 1 - ease((tn - t_out) / 0.3)
        for ta, L, x, y in items:
            if tn < ta: continue
            p = ease((tn - ta) / 0.3)
            put(fr, L, x, y + int(22 * (1 - p)), p * o)

# ---------------------------------------------------------------- audio (pieces placed on the timeline; overlaps crossfade)
cutwav = os.path.join(TMP, "cut.wav")
fl = []
for i, (o0, o1, s, ci) in enumerate(timeline):
    last_of = i + 1 == len(timeline) or timeline[i + 1][3] != ci
    first_of = i == 0 or timeline[i - 1][3] != ci
    fo = 0.25 if last_of else 0.015
    fl.append(f"[0:a]atrim={s:.3f}:{s + o1 - o0:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={0.08 if first_of else 0.015},"
              f"afade=t=out:st={max(0, o1 - o0 - fo):.3f}:d={fo},adelay={int(round(o0 * 1000))}:all=1[a{i}];")
mix = "".join(fl) + "".join(f"[a{i}]" for i in range(len(timeline))) + f"amix=inputs={len(timeline)}:normalize=0,apad=whole_dur={TOTAL:.3f}[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-filter_complex", mix, "-map", "[a]", "-ar", "48000", "-t", f"{TOTAL:.3f}", cutwav], check=True)
VOICE = ("highpass=f=80,afftdn=nr=8:nf=-45,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2.5,highshelf=f=9000:g=1.5,"
         "deesser=i=0.3,acompressor=threshold=0.1:ratio=2.5:attack=8:release=150:makeup=1.5")
_m = subprocess.run(["ffmpeg", "-hide_banner", "-i", cutwav, "-af", VOICE + ",loudnorm=I=-14:TP=-1:LRA=7:print_format=json", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
_j = json.loads(_m[_m.rindex("{"):_m.rindex("}") + 1])
VOICE += (f",loudnorm=I=-14:TP=-1:LRA=7:measured_I={_j['input_i']}:measured_TP={_j['input_tp']}:measured_LRA={_j['input_lra']}:"
          f"measured_thresh={_j['input_thresh']}:offset={_j['target_offset']}:linear=true")

# ---------------------------------------------------------------- render
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", cutwav, "-map", "0:v", "-map", "1:a", "-af", VOICE, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                        "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", OUT],
                       stdin=subprocess.PIPE)
def put(fr, L, x, y, a):
    hh, ww = min(L.shape[0], H - y), min(L.shape[1], W - x)
    L = L[:hh, :ww]; sub = fr[y:y + hh, x:x + ww]; al = L[..., 3:4] * a
    sub[:] = sub * (1 - al) + L[..., :3] * 255 * al
last = None
for fi in range(int(round(TOTAL * FPS))):
    tn = fi / FPS
    if tn < BODY:
        acc, wsum = np.zeros((H, W, 3), np.float32), 0.0
        for st, ci in srcs_at(tn):
            wgt = weight(tn, ci)
            if wgt <= 0.001: continue
            z = 1.0 + 0.05 * ease((tn - SPAN[ci][0]) / max(1.0, SPAN[ci][1] - SPAN[ci][0]))   # slow push-in per clip
            v = closeup(min(int(round(st * FPS)), N - 1), z)
            if ci == 0: v = bw(v, fi)
            acc += v * wgt; wsum += wgt
        fr = acc / max(wsum, 1e-6)
        if tn < 0.5: fr = fr * ease(tn / 0.5)
        last = fr.copy()
        for s, e, L in caps:
            if s - 0.02 <= tn < e:
                p = ease((tn - s) / 0.18); q = 1 - ease((tn - (e - 0.15)) / 0.15)
                sc = 0.94 + 0.06 * p
                Ls = cv2.resize(L, (int(L.shape[1] * sc), int(L.shape[0] * sc)), interpolation=cv2.INTER_AREA) if sc < 0.999 else L
                put(fr, Ls, (W - Ls.shape[1]) // 2, CAP_CY - Ls.shape[0] // 2, p * q); break
        draw_edu(fr, tn)
        if CRED_T[0] <= tn < CRED_T[1]:
            a = ease((tn - CRED_T[0]) / 0.5) * (1 - ease((tn - (CRED_T[1] - 0.5)) / 0.5))
            put(fr, CRED, CRED_XY[0] + int(40 * (1 - a)), CRED_XY[1], a)
    else:
        u = tn - BODY
        blur = cv2.GaussianBlur(last, (0, 0), 26) * 0.55
        mb = ease(u / END_XF); fr = last * (1 - mb) + blur * mb
        ca = ease((u - 0.1) / 0.3)
        if ca > 0: put(fr, CTA, (W - CTA.shape[1]) // 2, (H - CTA.shape[0]) // 2, ca)
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", OUT)

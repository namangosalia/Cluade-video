"""Podcast clips 4.1.1 + 4.1.2 (Gunjan Talks), kept as a podcast: 16:9, original frame, plain captions.

Naman's notes: not an explainer, not Instagram-style. While he describes the risk coming down to
moderate / low, the video cuts to his exact "Longitudinal Cardiovascular Prevention" picture (heart kept,
AnginaX logo removed) and only its risk curve animates: it draws from High to Moderate to Low, then on.

(Original explainer notes below, for reference.)

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
TMP = os.path.join(HERE, ".tmp_pod"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "risk_to_low_podcast_16x9.mp4")
W, H, FPS = 1920, 1080, 25
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
OUTRO = 4.0                                   # soft dissolve, then "Learn about your HeartPass" held 3 s
TOTAL = BODY + OUTRO
print(f"{len(keep)} pieces, body {BODY:.1f}s (raw {DUR:.1f}s)")


# ---------------------------------------------------------------- the picture: logo out, curve animatable
PIC = cv2.imread(os.path.join(HERE, "img", "reference.jpg"))
lx0, lx1, ly0, ly1 = 70, 300, 780, 890                        # AnginaX logo, bottom-left
reg = PIC[ly0:ly1, lx0:lx1]; bgm = cv2.medianBlur(reg, 31)
m = np.zeros(PIC.shape[:2], np.uint8); m[ly0:ly1, lx0:lx1] = ((np.abs(reg.astype(int) - bgm.astype(int)).max(2) > 18) * 255).astype(np.uint8)
m = cv2.dilate(m, np.ones((7, 7), np.uint8))
PIC = cv2.inpaint(PIC, m, 9, cv2.INPAINT_TELEA)
soft = cv2.GaussianBlur(PIC, (0, 0), 6); mm = cv2.GaussianBlur((m > 0).astype(np.float32), (0, 0), 8)[..., None]
PIC = (PIC * (1 - mm) + soft * mm).astype(np.uint8)
PIC_F = cv2.cvtColor(PIC, cv2.COLOR_BGR2RGB).astype(np.float32)
# chart without its curve: smooth card background fitted from the blue background pixels of the plot area
X0, X1, Y0, Y1 = 841, 1625, 322, 593
hsv = cv2.cvtColor(PIC, cv2.COLOR_BGR2HSV)
cand = (hsv[..., 0] >= 95) & (hsv[..., 0] <= 130) & (hsv[..., 2] < 140)
yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32); xn = (xx - X0) / (X1 - X0); yn = (yy - Y0) / (Y1 - Y0)
A = lambda x, y: np.stack([np.ones_like(x), x, y, x * x, y * y, x * y, x ** 3, y ** 3], -1)
cm = cand[Y0:Y1, X0:X1]
BASE = PIC_F.copy()
for c in range(3):
    coef, *_ = np.linalg.lstsq(A(xn[cm], yn[cm]), PIC_F[Y0:Y1, X0:X1, c][cm], rcond=None)
    fit = A(xn, yn) @ coef
    wgt = np.clip((yy - Y0) / 22, 0, 1) * np.clip((X1 - xx) / 14, 0, 1)        # feather into the card at top / right
    BASE[Y0:Y1, X0:X1, c] = PIC_F[Y0:Y1, X0:X1, c] * (1 - wgt) + fit * wgt
PILLS = [(895, (872, 1010, 326, 368)), (1068, (1068, 1252, 408, 450)), (1324, (1320, 1460, 470, 512))]   # dot x, pill box
def picture(wipe_x):
    """the exact picture with the curve drawn up to wipe_x (image px); pills fade in as the line reaches them"""
    out = BASE.copy()
    xs = np.arange(X0, X1, dtype=np.float32)
    a = np.clip((wipe_x - xs) / 30.0 + 0.5, 0, 1)[None, :, None]
    out[Y0:Y1, X0:X1] = BASE[Y0:Y1, X0:X1] * (1 - a) + PIC_F[Y0:Y1, X0:X1] * a
    for dot_x, (bx0, bx1, by0, by1) in PILLS:                  # pills: appear whole, softly
        pa = float(np.clip((wipe_x - dot_x) / 40.0, 0, 1))
        out[by0:by1, bx0:bx1] = BASE[by0:by1, bx0:bx1] * (1 - pa) + PIC_F[by0:by1, bx0:bx1] * pa
        if pa > 0 and dot_x < wipe_x:                          # keep the reveal under the pill consistent
            pass
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_CUBIC)

T_IN, T_OUT = TW(11) - 0.3, remap(words[61][1]) + 1.2        # picture card: "like every 3-6 months ..." -> "... maintain low risk."
# slow: the line eases down High -> Moderate -> Low across his sentence, then carries on while he says "maintain"
WIPE = [(T_IN + 1.2, 841), (TW(27), 895), (TW(32) + 0.2, 1068), (TW(34) + 1.0, 1380), (TW(55), 1380), (TW(55) + 3.0, 1625)]
# the card sits bottom-right, below his chin (face never lower than y~680 in 1080), with rounded corners + shadow
IW, IH = 840, 473
IX, IY = W - IW - 44, H - IH - 40
IMASK = Image.new("L", (IW, IH), 0); ImageDraw.Draw(IMASK).rounded_rectangle((0, 0, IW - 1, IH - 1), 22, fill=255)
IMASK = (np.asarray(IMASK).astype(np.float32) / 255)[..., None]
_sh = Image.new("L", (IW + 80, IH + 80), 0); ImageDraw.Draw(_sh).rounded_rectangle((40, 52, 40 + IW, 52 + IH), 22, fill=170)
ISHADOW = (np.asarray(_sh.filter(ImageFilter.GaussianBlur(18))).astype(np.float32) / 255)[..., None]
def wipe_at(t):
    xs_ = [w_[1] for w_ in WIPE]; ts_ = [w_[0] for w_ in WIPE]
    if t <= ts_[0]: return 841.0 - 40
    return float(np.interp(t, ts_, xs_))
_pic_cache = {}
def pic_at(t):
    key = int(round(wipe_at(t)))
    if key not in _pic_cache:
        if len(_pic_cache) > 6: _pic_cache.clear()
        _pic_cache[key] = picture(key)
    return _pic_cache[key]

# ---------------------------------------------------------------- captions: plain podcast subtitles at the bottom
F_BODY = F("Inter-Medium.otf", 40); F_HL = F("Inter-SemiBold.otf", 40)
MAXW, LH = 1500, 52
GROUPS = [
    (0, 16, "What we have seen is, over a period of 9 months, like every 3–6 months,"),
    (18, 25, "there's a follow-up for those patients,"),
    (25, 35, "and the risk has come down to moderate or low."),
    (47, 55, "We want to reduce everyone's risk to low"),
    (55, 62, "and let them maintain low risk."),
    (62, 73, "Just go to any doctor that you prefer, your family doctor."),
    (73, 80, "Get your tests done. Do your AnginaX."),
    (80, 86, "If your doctors don't have it,"),
    (86, 96, "call them up and say, “I want to do my AnginaX.”"),
    (102, 109, "Eventually, this will be in India completely."),
    (109, 118, "But this is how we're going to save lives."),
]
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text, cx=W / 2, maxw=MAXW):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_BODY) > maxw: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    hgt = LH * len(lines) + 40
    img = Image.new("RGBA", (W, hgt), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines):
        ds.text((cx, 22 + i * LH + 3), ln, font=F_BODY, fill=230, anchor="ma")
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(5)))
    img = Image.alpha_composite(img, shadow); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((cx, 22 + i * LH), ln, font=F_BODY, fill=(255, 255, 255, 255), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
caps = []
for gi, (i0, i1, text) in enumerate(GROUPS):
    s0 = TW(i0); e0 = remap(words[i1 - 1][1]) + 0.5
    if gi + 1 < len(GROUPS): e0 = min(e0, TW(GROUPS[gi + 1][0]) - 0.04) if TW(GROUPS[gi + 1][0]) - e0 < 0.6 else e0
    caps.append((s0, e0, cap_layer(text), cap_layer(text, cx=(IX - 30) / 2 + 10, maxw=IX - 90)))
CAP_BOTTOM = H - 46

# ---------------------------------------------------------------- end card button
def make_cta(text):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); f = F("Inter-SemiBold.otf", 40); track = 6
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
CTA = make_cta("LEARN ABOUT YOUR HEARTPASS")

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
last = None
BLUR_LAST = None
for fi in range(int(round(TOTAL * FPS))):
    t = fi / FPS
    if t < BODY:
        k = int(round(unmap(t) * FPS))
        fr = cv2.resize(src_frame(k), (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        fr = fr * 1.25 - cv2.GaussianBlur(fr, (0, 0), 1.6) * 0.25
        last = fr
    else:
        u = t - BODY                                            # end card: soft colour blur + HeartPass button (3 s)
        mb = ease(u / 0.7)
        if BLUR_LAST is None: BLUR_LAST = cv2.GaussianBlur(last, (0, 0), 26) * 0.6
        fr = last * (1 - mb) + BLUR_LAST * mb
        ca = ease((u - 0.5) / 0.5)
        if ca > 0:
            y0, x0 = (H - CTA.shape[0]) // 2, (W - CTA.shape[1]) // 2
            al = CTA[..., 3:4] * ca
            fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] = fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] * (1 - al) + CTA[..., :3] * 255 * al
    m_ = ease((t - T_IN) / 1.0) * (1 - ease((t - T_OUT) / 0.8))          # the card slides up and fades in slowly
    if m_ > 0 and t < BODY:
        card = cv2.resize(pic_at(t), (IW, IH), interpolation=cv2.INTER_AREA)
        yo = IY + int(round(30 * (1 - m_)))
        sh_ = ISHADOW * m_ * 0.8
        ys0 = yo - 52; ys1 = min(H, ys0 + IH + 80); xs1 = min(W, IX - 40 + IW + 80)
        fr[ys0:ys1, IX - 40:xs1] *= (1 - sh_[: ys1 - ys0, : xs1 - (IX - 40)])
        hv = min(IH, H - yo)
        sub = fr[yo:yo + hv, IX:IX + IW]
        sub[:] = sub * (1 - IMASK[:hv] * m_) + card[:hv] * IMASK[:hv] * m_
    for s, e, Lc, Ll in caps:
        L = Ll if (T_IN <= t < T_OUT + 0.8) else Lc
        if s - 0.02 <= t < e:
            a = ease((t - s) / 0.15) * (1 - ease((t - (e - 0.15)) / 0.15))
            hh = L.shape[0]; y = CAP_BOTTOM - hh + 20
            sub = fr[y:y + hh]; al = L[..., 3:4] * a
            fr[y:y + hh] = sub * (1 - al) + L[..., :3] * 255 * al
            break
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", OUT)

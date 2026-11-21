"""HeartPass podcast reel, clean version (Naman's notes on the engine cut):

- no AnginaX logo, no full-screen statements, no greyed / black-and-white moments
- small white captions underneath the picture, key words highlighted in colour (word by word)
- gentle framing: a 4:5 window of the 16:9 camera (about 1.9x, was 2.7x + zooms) that follows the speaker
  slowly; shots showing the podcast's burned-in question title are framed so it stays out
- the same cuts as config.py (fillers, false starts, hesitation gaps), ending on "Learn about your HeartPass"
"""
import json, os, runpy, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, ".tmp_clean"); os.makedirs(TMP, exist_ok=True)
OUT = os.path.join(HERE, "output", "heartpass_podcast_clean_9x16.mp4")
CFG = runpy.run_path(os.path.join(HERE, "config.py"))
W, H, FPS = 1080, 1920, 25
PW, PH, PY = 1080, 1350, 120              # picture (4:5) and its top edge; captions sit underneath it
CAP_Y = PY + PH + 34                      # top of the caption lines
END_CARD, END_DUR = "LEARN ABOUT YOUR HEARTPASS", 3.0
INTER = "/usr/share/fonts/opentype/inter/"
HL = (120, 182, 255)                      # highlight colour for key words (soft blue)

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- sources, words
parts = [os.path.join(HERE, "raw", f"part{i}.mp4") for i in range(1, 5)]
lst = os.path.join(TMP, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
comb = os.path.join(TMP, "combined.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", comb], check=True)
words = json.load(open(os.path.join(HERE, "words.json")))

# ---------------------------------------------------------------- cuts: hesitation gaps + config's CUT_TIMES
wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a16 = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
DUR = len(a16) / 16000
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
SIL = min(-30.0, float(np.percentile(rms[rms > -90], 90)) - 20.0)
MIN_PAUSE, KEEP, KEEP_LONG = CFG["MIN_PAUSE"], CFG["PAUSE_KEEP"], CFG["PAUSE_KEEP_LONG"]
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
cuts += CFG["CUT_TIMES"]
END_T = words[-1][1] + 0.35
cuts.append((END_T, DUR + 1))
cuts.sort(); merged = []
for s, e in cuts:
    if merged and s <= merged[-1][1]: merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
    else: merged.append((s, e))
keep, t0 = [], max(0.0, words[0][0] - 0.05)
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
print(f"{len(keep)} pieces, body {BODY:.1f}s (raw {DUR:.1f}s)")

# ---------------------------------------------------------------- framing per original frame (follows the speaker)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(comb); SW, SH = int(cap.get(3)), int(cap.get(4))
faces, hists, title = [], [], []
while True:
    ok, f = cap.read()
    if not ok: break
    small = cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA)
    h = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256])
    hists.append(cv2.normalize(h, h).flatten())
    band = f[575:700, 100:1180].min(2) > 225
    title.append(band.any(0).sum() > 500 and band.sum() > 1500)
    d = fc.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(40, 40))
    faces.append(max(d, key=lambda b: b[2]) if len(d) else None)
N = len(hists)
shots = [0] + [k for k in range(1, N) if cv2.compareHist(hists[k - 1], hists[k], cv2.HISTCMP_BHATTACHARYYA) > 0.35] + [N]
BH, TH = SH, 566                                 # window height: full, or stopping above the burned-in title
win = np.zeros((N, 3), np.float32)               # x0, width, height
for a, b in zip(shots, shots[1:]):
    ks = [k for k in range(a, b) if faces[k] is not None]
    if ks:
        fx = np.array([(faces[k][0] + faces[k][2] / 2) * SW / 640 for k in ks], np.float32)
        fx = np.array([np.median(fx[max(0, j - 6):j + 7]) for j in range(len(fx))])
        cx = np.interp(np.arange(a, b), ks, fx)
        ker = np.exp(-0.5 * (np.arange(-40, 41) / 18.0) ** 2); ker /= ker.sum()
        cx = np.convolve(np.pad(cx, 40, mode="edge"), ker, mode="same")[40:-40]
    else:
        cx = np.full(b - a, SW / 2)
    hh = TH if any(title[a:b]) else BH
    ww = hh * PW / PH
    win[a:b, 0] = np.clip(cx - ww / 2, 0, SW - ww); win[a:b, 1] = ww; win[a:b, 2] = hh

# ---------------------------------------------------------------- captions: small white, key words highlighted, word by word
F_BODY = ImageFont.truetype(INTER + "Inter-Medium.otf", 46)
F_HL = ImageFont.truetype(INTER + "Inter-Bold.otf", 46)
MAXW, LH = 960, 62
GROUPS = [
    (0, 7, "The rate of [heart attacks] is increasing"),
    (16, 19, "in [India,] specifically."),
    (19, 32, "However, we know these problems are directly related with things like [obesity.]"),
    (32, 45, "And if we look at obesity, this is more in [western countries.]"),
    (45, 57, "For example, the rate of obesity in the [US] is much higher."),
    (57, 69, "Even then, there are not as many [heart problems] as in India."),
    (69, 72, "[Why is that?]"),
    (74, 79, "There are [two sections] here."),
    (79, 90, "It's not that only [obese people] are getting heart attacks, right?"),
    (90, 103, "People who are not obese, or they're fit, they [also get heart attacks.]"),
    (103, 110, "Let's talk about [Indians] getting heart attacks."),
    (110, 120, "Indians are getting heart attacks [more,] which is [not true,]"),
    (120, 127, "because we're not comparing [apples to apples.]"),
    (130, 133, "It's [not cosmetic.]"),
    (133, 139, "It's more of a [metabolic phenotype.]"),
    (139, 146, "We have the [Lp(a)] marker as [South Asians.]"),
    (146, 152, "We obviously are [metabolically ill] more."),
    (152, 164, "And I don't think it's comparable, because they are [also] metabolically ill."),
    (164, 171, "There are a lot of [different factors.]"),
    (171, 179, "So we can't really compare [western versus Indian.]"),
    (179, 185, "But let's talk about [Indians] only."),
    (185, 192, "We are the [diabetes capital] of the world."),
    (192, 197, "We have a [high-carb diet.]"),
    (197, 203, "We don't do [prevention] that much."),
    (207, 217, "I think that [delay] is also one of the aspects,"),
    (217, 227, "that we are meeting our cardiologist in the [ICU room,]"),
    (227, 233, "which should [not] be the case,"),
    (233, 241, "even after having the [best medical facilities.]"),
]

def tokens(text):
    out, hl = [], False
    for raw in text.split():
        st = raw.startswith("["); en = raw.endswith("]")
        if st: hl = True
        out.append((raw.strip("[]"), hl))
        if en: hl = False
    return out

dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def tw(word, h): return dd.textlength(word, font=F_HL if h else F_BODY)
SPACE = dd.textlength(" ", font=F_BODY)

def layout(toks):
    """balanced lines (max 2 normally); returns [(x, y, word, hl)] relative to a W-wide block"""
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
        lw = sum(widths[i] for i in idx) + SPACE * (len(idx) - 1)
        x = (W - lw) / 2
        for i in idx:
            pos.append((x, li * LH, toks[i][0], toks[i][1])); x += widths[i] + SPACE
    return pos

def word_layer(word, hl):
    f = F_HL if hl else F_BODY
    wdt = int(tw(word, hl)) + 40; img = Image.new("RGBA", (wdt, 90), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).text((20, 14), word, font=f, fill=200)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(6)))
    img = Image.alpha_composite(img, shadow)
    ImageDraw.Draw(img).text((20, 10), word, font=f, fill=(HL if hl else (255, 255, 255)) + (255,))
    return np.asarray(img).astype(np.float32) / 255

caps = []
for gi, (i0, i1, text) in enumerate(GROUPS):
    toks = tokens(text); n_w = i1 - i0
    times = [remap(words[i0 + min(int(round(j * n_w / len(toks))), n_w - 1)][0]) for j in range(len(toks))]
    end = remap(words[i1 - 1][1]) + 0.6
    if gi + 1 < len(GROUPS): end = min(end, remap(words[GROUPS[gi + 1][0]][0]) - 0.04) if remap(words[GROUPS[gi + 1][0]][0]) - end < 0.6 else end
    pos = layout(toks)
    caps.append((times[0], end, [(t, x, y, word_layer(wd, h)) for t, (x, y, wd, h) in zip(times, pos)]))

# name title, small, over the top of the picture when Naman first speaks
def name_layer():
    img = Image.new("RGBA", (W, 140), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(INTER + "Inter-SemiBold.otf", 40); f2 = ImageFont.truetype(INTER + "Inter-Regular.otf", 28)
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    ds.text((62, 22), "Naman Gosalia", font=f1, fill=200); ds.text((62, 78), "Founder, AnginaX  ·  Gunjan Talks", font=f2, fill=200)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(7)))
    img = Image.alpha_composite(img, shadow); d = ImageDraw.Draw(img)
    d.text((60, 18), "Naman Gosalia", font=f1, fill=(255, 255, 255, 255))
    d.text((60, 74), "Founder, AnginaX  ·  Gunjan Talks", font=f2, fill=(220, 226, 236, 255))
    return np.asarray(img).astype(np.float32) / 255
NAME = name_layer(); NAME_T = (remap(words[74][0]), remap(words[74][0]) + 4.5)

def make_cta(text):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); size, track = 36, 5
    f = ImageFont.truetype(INTER + "Inter-SemiBold.otf", size)
    widths = [d.textlength(ch, font=f) for ch in text]; t_w = sum(widths) + track * (len(text) - 1)
    pw, ph, pad = int(t_w + 140), 100, 30
    img = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + pw, pad + ph + 8), ph // 2, fill=110)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14))); dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((pad, pad, pad + pw, pad + ph), ph // 2, fill=(255, 255, 255, 255))
    x = pad + (pw - t_w) / 2; asc, desc = f.getmetrics(); y = pad + (ph - (asc + desc)) / 2 + 2
    for ch, wd in zip(text, widths):
        dr.text((x, y), ch, font=f, fill=(34, 36, 40, 255)); x += wd + track
    return np.asarray(img).astype(np.float32) / 255
CTA = make_cta(END_CARD)

# ---------------------------------------------------------------- audio: cut, clean podcast voice, level
cutwav = os.path.join(TMP, "cut.wav")
fc_a = "".join(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:st={max(0, e - s - 0.015):.3f}:d=0.015[a{i}];"
               for i, (s, e) in enumerate(keep)) + "".join(f"[a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=0:a=1[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-filter_complex", fc_a, "-map", "[a]", "-ar", "48000", cutwav], check=True)
VOICE = ("highpass=f=70,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2.5,highshelf=f=9000:g=1.5,"
         "deesser=i=0.3,acompressor=threshold=0.1:ratio=2.5:attack=8:release=150:makeup=1.5,"
         f"apad=pad_dur={END_DUR + 0.2},loudnorm=I=-14:TP=-1:LRA=7")
TOTAL = BODY + END_DUR

# ---------------------------------------------------------------- picture
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", comb, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
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
for fi in range(int(round(TOTAL * FPS))):
    t = fi / FPS
    if t < BODY:
        k = min(int(round(unmap(t) * FPS)), N - 1)
        fr_src = src_frame(k)
        x0, ww, hh = win[k]
        pic = cv2.resize(fr_src[: int(hh), int(x0): int(x0 + ww)], (PW, PH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        pic = pic * 1.25 - cv2.GaussianBlur(pic, (0, 0), 1.6) * 0.25
        # colour background: the same shot, softly blurred and dimmed
        bg = cv2.resize(fr_src, (W // 20, int(W // 20 * SH / SW)), interpolation=cv2.INTER_AREA)
        bg = cv2.resize(cv2.GaussianBlur(bg, (0, 0), 1.5), (int(H * SW / SH), H), interpolation=cv2.INTER_CUBIC)
        ox = (bg.shape[1] - W) // 2
        fr = bg[:, ox:ox + W].astype(np.float32) * 0.42
        fr[PY:PY + PH] = pic
        last = fr.copy()
        for s, e, wl in caps:
            if s - 0.02 <= t < e:
                out = 1 - ease((t - (e - 0.2)) / 0.2)
                for tt_, x, y, L in wl:
                    if t >= tt_ - 0.02:
                        aa = ease((t - tt_ + 0.02) / 0.16) * out
                        X, Y = int(x) - 20, CAP_Y + y - 10
                        hL, wL = L.shape[:2]
                        sub = fr[Y:Y + hL, X:X + wL]; al = L[: sub.shape[0], : sub.shape[1], 3:4] * aa
                        sub[:] = sub * (1 - al) + L[: sub.shape[0], : sub.shape[1], :3] * 255 * al
                break
        if NAME_T[0] <= t < NAME_T[1]:
            na = ease((t - NAME_T[0]) / 0.4) * (1 - ease((t - (NAME_T[1] - 0.4)) / 0.4))
            Y = PY + 24; al = NAME[..., 3:4] * na
            fr[Y:Y + 140] = fr[Y:Y + 140] * (1 - al) + NAME[..., :3] * 255 * al
    else:
        # end card in colour: the last picture softly blurred, then the HeartPass button
        u = t - BODY
        m = ease(u / 0.8)
        blur = cv2.GaussianBlur(last, (0, 0), 24) * 0.55
        fr = last * (1 - m) + blur * m
        a = ease((u - 0.5) / 0.5)
        if a > 0:
            y0, x0 = (H - CTA.shape[0]) // 2, (W - CTA.shape[1]) // 2
            al = CTA[..., 3:4] * a
            fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] = fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] * (1 - al) + CTA[..., :3] * 255 * al
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", OUT)

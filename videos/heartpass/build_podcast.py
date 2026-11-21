"""HeartPass podcast clip (Gunjan Talks) kept as a podcast, same treatment as videos/risk_low/build_podcast.py:

- 16:9, the original podcast frame (podcast logo as it is), plain white captions at the bottom; not an explainer
- photos as soft cards on the right, clear of the speaker's face, slowly in and out:
  "only obese people ..." -> img/obese.jpg, "people who are fit also get heart attacks" -> img/fit_chest_pain.jpg
- the same cuts as config.py; it ends on "...in the ICU room, which should not be the case."
  (the camera cuts to the host on the final syllable, so Naman's last frame is held for that tenth of a second)
- then a soft colour blur and "LEARN ABOUT YOUR HEARTPASS" held for 3 s
"""
import json, os, runpy, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, ".tmp_pod"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "heartpass_podcast_16x9.mp4")
CFG = runpy.run_path(os.path.join(HERE, "config.py"))
W, H, FPS = 1920, 1080, 25
INTER = "/usr/share/fonts/opentype/inter/"
def F(name, size): return ImageFont.truetype(INTER + name, size)
def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- sources, cuts
parts = [os.path.join(HERE, "raw", f"part{i}.mp4") for i in range(1, 5)]
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
END_T = 84.99                                  # "...which should not be the case." ("case" decays by 84.98)
LAST_NAMAN = 84.83                             # the source cuts to the host at 84.85
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
TW = lambda i: remap(words[i][0])
OUTRO = 4.0
TOTAL = BODY + OUTRO
print(f"{len(keep)} pieces, body {BODY:.1f}s (raw {DUR:.1f}s)")

# ---------------------------------------------------------------- photo cards (right side, clear of the face)
CARD_W = 560
def card(path):
    im = Image.open(path).convert("RGB")
    h = int(round(CARD_W * im.height / im.width)); h = min(h, 560)
    im = im.resize((int(round(h * im.width / im.height)) if h == 560 else CARD_W, h), Image.LANCZOS)
    return np.asarray(im).astype(np.float32)
def rounded(w_, h_, r=22):
    m = Image.new("L", (w_, h_), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w_ - 1, h_ - 1), r, fill=255)
    return (np.asarray(m).astype(np.float32) / 255)[..., None]
def shadow(w_, h_, r=22):
    s = Image.new("L", (w_ + 80, h_ + 80), 0); ImageDraw.Draw(s).rounded_rectangle((40, 52, 40 + w_, 52 + h_), r, fill=170)
    return (np.asarray(s.filter(ImageFilter.GaussianBlur(18))).astype(np.float32) / 255)[..., None]
CARDS = []
for path, w0, w1 in (("img/obese.jpg", 79, 90), ("img/fit_chest_pain.jpg", 90, 103)):
    im = card(os.path.join(HERE, path)); ch, cw = im.shape[:2]
    t_in = TW(w0) - 0.2; t_out = remap(words[w1 - 1][1]) + 0.3
    CARDS.append(dict(img=im, w=cw, h=ch, x=W - cw - 50, y=H - ch - 50, t_in=t_in, t_out=t_out,
                      mask=rounded(cw, ch), sh=shadow(cw, ch)))
# back-to-back cards: the first fades as the second arrives
CARDS[0]["t_out"] = min(CARDS[0]["t_out"], CARDS[1]["t_in"] + 0.6)

def draw_card(fr, c, t):
    a = ease((t - c["t_in"]) / 0.8) * (1 - ease((t - c["t_out"]) / 0.7))
    if a <= 0: return False
    u = (t - c["t_in"]) / max(0.1, c["t_out"] - c["t_in"])
    z = 1.0 + 0.05 * u                                          # slow push-in inside the card
    img = c["img"]; hh, ww = img.shape[:2]
    cw_, ch_ = int(ww / z), int(hh / z); x0 = (ww - cw_) // 2; y0 = (hh - ch_) // 2
    pic = cv2.resize(img[y0:y0 + ch_, x0:x0 + cw_], (ww, hh), interpolation=cv2.INTER_AREA)
    yo = c["y"] + int(round(26 * (1 - a)))
    ys0 = yo - 52; ys1 = min(H, ys0 + hh + 80); xs0 = c["x"] - 40; xs1 = min(W, xs0 + ww + 80)
    fr[ys0:ys1, xs0:xs1] *= (1 - c["sh"][: ys1 - ys0, : xs1 - xs0] * a * 0.8)
    hv = min(hh, H - yo)
    sub = fr[yo:yo + hv, c["x"]:c["x"] + ww]
    sub[:] = sub * (1 - c["mask"][:hv] * a) + pic[:hv] * c["mask"][:hv] * a
    return True

# ---------------------------------------------------------------- captions: plain podcast subtitles
F_BODY = F("Inter-Medium.otf", 40)
LH = 52
GROUPS = [
    (0, 7, "The rate of heart attacks is increasing"),
    (16, 19, "in India, specifically."),
    (19, 32, "However, we know these problems are directly related with things like obesity."),
    (32, 45, "And if we look at obesity, this is more in western countries."),
    (45, 57, "For example, the rate of obesity in the US is much higher."),
    (57, 72, "Even then, there are not as many heart problems as in India. Why is that?"),
    (74, 79, "There are two sections here."),
    (79, 90, "It's not that only obese people are getting heart attacks, right?"),
    (90, 103, "People who are not obese, or they're fit, they also get heart attacks."),
    (103, 110, "Let's talk about Indians getting heart attacks."),
    (110, 120, "Indians are getting heart attacks more, which is not true,"),
    (120, 127, "because we're not comparing apples to apples."),
    (130, 139, "It's not cosmetic. It's more of a metabolic phenotype."),
    (139, 146, "We have the Lp(a) marker as South Asians."),
    (146, 152, "We obviously are metabolically ill more."),
    (152, 164, "And I don't think it's comparable, because they are also metabolically ill."),
    (164, 171, "There are a lot of different factors."),
    (171, 179, "So we can't really compare western versus Indian."),
    (179, 185, "But let's talk about Indians only."),
    (185, 192, "We are the diabetes capital of the world."),
    (192, 197, "We have a high-carb diet."),
    (197, 203, "We don't do prevention that much."),
    (207, 217, "I think that delay is also one of the aspects,"),
    (217, 227, "that we are meeting our cardiologist in the ICU room,"),
    (227, 233, "which should not be the case."),
]
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text, cx, maxw):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_BODY) > maxw: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    hgt = LH * len(lines) + 40
    img = Image.new("RGBA", (W, hgt), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines): ds.text((cx, 22 + i * LH + 3), ln, font=F_BODY, fill=230, anchor="ma")
    sd = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd.putalpha(sh.filter(ImageFilter.GaussianBlur(5)))
    img = Image.alpha_composite(img, sd); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines): d.text((cx, 22 + i * LH), ln, font=F_BODY, fill=(255, 255, 255, 255), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
LEFT_W = W - CARD_W - 50 - 60                       # caption area beside a card
caps = []
for gi, (i0, i1, text) in enumerate(GROUPS):
    s0 = TW(i0); e0 = remap(words[i1 - 1][1]) + 0.5
    if gi + 1 < len(GROUPS):
        nx = TW(GROUPS[gi + 1][0]) - 0.04
        if nx - e0 < 0.6: e0 = nx
    caps.append((s0, e0, cap_layer(text, W / 2, 1500), cap_layer(text, LEFT_W / 2 + 20, LEFT_W - 60)))
CAP_BOTTOM = H - 46
CARD_SPAN = (CARDS[0]["t_in"], CARDS[1]["t_out"] + 0.7)

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
SW, SH = 1280, 720
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
# frames where the podcast's own question title is burned in at the bottom: lift our captions above it
TITLE = []
_cap = cv2.VideoCapture(comb)
while True:
    ok, f_ = _cap.read()
    if not ok: break
    band = f_[575:700, 100:1180].min(2) > 225
    TITLE.append(band.any(0).sum() > 500 and band.sum() > 1500)
TITLE = np.array(TITLE)
TITLE = np.convolve(TITLE.astype(float), np.ones(13) / 13, mode="same") > 0.2     # steady on/off
last, blur_last = None, None
for fi in range(int(round(TOTAL * FPS))):
    t = fi / FPS
    if t < BODY:
        k = int(round(min(unmap(t), LAST_NAMAN) * FPS))
        fr = cv2.resize(src_frame(k), (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        fr = fr * 1.25 - cv2.GaussianBlur(fr, (0, 0), 1.6) * 0.25
        last = fr.copy()
        for c in CARDS: draw_card(fr, c, t)
        for s, e, Lc, Ll in caps:
            if s - 0.02 <= t < e:
                L = Ll if CARD_SPAN[0] <= t < CARD_SPAN[1] else Lc
                a = ease((t - s) / 0.15) * (1 - ease((t - (e - 0.15)) / 0.15))
                hh = L.shape[0]
                y = (CAP_BOTTOM if not TITLE[min(k, len(TITLE) - 1)] else int(570 * 1.5) - 10) - hh + 20
                al = L[..., 3:4] * a
                fr[y:y + hh] = fr[y:y + hh] * (1 - al) + L[..., :3] * 255 * al
                break
    else:
        u = t - BODY                                             # soft colour blur, then the HeartPass button for 3 s
        if blur_last is None: blur_last = cv2.GaussianBlur(last, (0, 0), 26) * 0.6
        mb = ease(u / 0.7); fr = last * (1 - mb) + blur_last * mb
        ca = ease((u - 0.5) / 0.5)
        if ca > 0:
            y0, x0 = (H - CTA.shape[0]) // 2, (W - CTA.shape[1]) // 2
            al = CTA[..., 3:4] * ca
            fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] = fr[y0:y0 + CTA.shape[0], x0:x0 + CTA.shape[1]] * (1 - al) + CTA[..., :3] * 255 * al
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", OUT)

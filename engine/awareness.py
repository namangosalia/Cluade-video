#!/usr/bin/env python3
"""Awareness reel: statement after statement over real photos in polluted air.

    python3 engine/awareness.py videos/<slug>/config.py

Config: SLIDES = [(image or None, [lines], seconds)], OUTPUT, END = (lines, seconds).
Each photo is cover-fitted to 9:16, slowly zoomed (alternating in / out), graded toward
smog (muted, warm-grey, lifted blacks) with drifting haze and floating particles.
Statements fade and rise slowly so they can be read. A missing image becomes a
smoggy-skyline placeholder so timing can be reviewed before the photos arrive.
Sound: original low city rumble + soft heartbeat under the heart lines (no music licence).
Output: 1080x1920 30 fps H.264 SDR (BT.709), AAC.
"""
import math, os, runpy, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
CFG = os.path.abspath(sys.argv[1]); VDIR = os.path.dirname(CFG)
C = runpy.run_path(CFG)
P = lambda p: p if os.path.isabs(p) else os.path.join(VDIR, p)
W, H, FPS = 1080, 1920, 30
ANTON = os.path.join(REPO, "assets", "fonts", "Anton-Regular.woff")
INTER = "/usr/share/fonts/opentype/inter/"
CREAM, WHITE, RED = (240, 214, 158), (255, 255, 255), (226, 60, 50)
rng = np.random.default_rng(11)
TMP = os.path.join(VDIR, ".tmp"); os.makedirs(TMP, exist_ok=True)

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

_f = {}
def font(kind, size):
    k = (kind, size)
    if k not in _f:
        _f[k] = ImageFont.truetype(ANTON if kind == "anton" else INTER + f"Inter-{kind}.otf", size)
    return _f[k]

# ------------------------------------------------------------------ backgrounds
def placeholder(seed):
    """Smoggy city skyline, used until the real photo is supplied."""
    r = np.random.default_rng(seed)
    img = Image.new("RGB", (W, H))
    arr = np.zeros((H, W, 3), np.float32)
    y = np.linspace(0, 1, H)[:, None, None]
    arr += np.array([150, 140, 120], np.float32) * (1 - y) + np.array([95, 88, 76], np.float32) * y
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for layer, (base, col) in enumerate([(1250, (120, 112, 98)), (1380, (90, 84, 74)), (1520, (62, 58, 52))]):
        x = -40
        while x < W:
            bw = r.integers(60, 170); bh = r.integers(150, 520) - layer * 60
            d.rectangle((x, base - bh, x + bw, H), fill=col)
            x += bw + r.integers(4, 30)
    sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sun).ellipse((640, 520, 820, 700), fill=(255, 210, 150, 120))
    img = img.convert("RGBA"); img.alpha_composite(sun.filter(ImageFilter.GaussianBlur(30)))
    return img.convert("RGB").filter(ImageFilter.GaussianBlur(2))

def load_bg(path, seed):
    if path and os.path.exists(P(path)):
        im = Image.open(P(path)).convert("RGB")
        s = max(W * 1.12 / im.width, H * 1.12 / im.height)      # headroom for the slow zoom
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        return im, True
    im = placeholder(seed)
    return im.resize((round(W * 1.12), round(H * 1.12)), Image.LANCZOS), False

def smog_grade(arr):
    """Muted, warm-grey, lifted blacks: the look of a hazy, polluted day."""
    lum = arr @ np.array([0.299, 0.587, 0.114], np.float32)
    arr = arr * 0.55 + lum[..., None] * 0.45                      # desaturate
    arr = arr * np.array([1.04, 1.0, 0.90], np.float32)           # warm-grey cast
    arr = 18 + arr * 0.86                                         # lift blacks, compress highs
    return arr

# drifting haze: two large soft noise fields, scrolled slowly
def noise_field(seed, scale):
    r = np.random.default_rng(seed)
    small = r.random((H // scale + 4, W // scale + 4)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(((W // scale + 4) * scale, (H // scale + 4) * scale), Image.BICUBIC)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(scale * 0.6))).astype(np.float32) / 255
HAZE1, HAZE2 = noise_field(3, 120), noise_field(4, 60)
PART = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.2, 3.2), rng.uniform(4, 16), rng.uniform(0, 6.28)) for _ in range(140)]

def haze(t):
    o1, o2 = int(t * 14) % 240, int(t * 26) % 120
    h1 = HAZE1[:H, o1:o1 + W] if HAZE1.shape[1] >= o1 + W else HAZE1[:H, :W]
    h2 = HAZE2[:H, o2:o2 + W] if HAZE2.shape[1] >= o2 + W else HAZE2[:H, :W]
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    return (0.22 + 0.20 * h1 + 0.10 * h2) * (0.75 + 0.25 * (1 - y))   # denser toward the sky

def particles(t):
    lay = Image.new("L", (W, H), 0); d = ImageDraw.Draw(lay)
    for x, y, r_, sp, ph in PART:
        xx = (x + sp * t * 3) % W; yy = (y - sp * t + 8 * math.sin(t * 0.7 + ph)) % H
        d.ellipse((xx - r_, yy - r_, xx + r_, yy + r_), fill=int(90 + 60 * math.sin(t + ph) ** 2))
    return np.asarray(lay.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255

# ------------------------------------------------------------------ text
def text_layer(lines, t, dur):
    """lines: [(text, style)]; style: big | key | red | body | small. Lines fade/rise in one by one."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    blocks = []
    for text, style in lines:
        if style in ("big", "key", "red"):
            size = 120 if style != "key" else 112
            f = font("anton", size)
            words, rows, cur = text.split(), [], ""
            for w_ in words:
                trial = (cur + " " + w_).strip()
                if d.textlength(trial, font=f) > W - 150 and cur:
                    rows.append(cur); cur = w_
                else:
                    cur = trial
            rows.append(cur)
            col = {"big": WHITE, "key": CREAM, "red": RED}[style]
            for r_ in rows:
                blocks.append((r_, f, col, 1.0))
        else:
            f = font("Medium" if style == "body" else "SemiBold", 52 if style == "body" else 38)
            words, rows, cur = text.split(), [], ""
            for w_ in words:
                trial = (cur + " " + w_).strip()
                if d.textlength(trial, font=f) > W - 170 and cur:
                    rows.append(cur); cur = w_
                else:
                    cur = trial
            rows.append(cur)
            for r_ in rows:
                blocks.append((r_, f, WHITE if style == "body" else CREAM, 1.35))
    heights = [(b[1].getmetrics()[0] + b[1].getmetrics()[1]) * (0.98 if b[3] == 1.0 else b[3]) for b in blocks]
    y = 1000 - sum(heights) / 2
    n = len(blocks)
    out_a = 1 - ease((t - (dur - 0.7)) / 0.7)
    for i, ((text, f, col, _), h) in enumerate(zip(blocks, heights)):
        t_in = 0.35 + i * min(0.55, (dur * 0.35) / max(n, 1))
        a = ease((t - t_in) / 0.8) * out_a
        rise = (1 - ease((t - t_in) / 1.2)) * 26 + t * 4               # slow continuous drift up
        if a > 0:
            tw = d.textlength(text, font=f)
            d.text(((W - tw) / 2, y - rise), text, font=f, fill=col + (int(255 * a),))
        y += h
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 1.6))))
    sh.alpha_composite(img)
    return np.asarray(sh).astype(np.float32) / 255

# ------------------------------------------------------------------ build
SLIDES = C["SLIDES"]; END_LINES, END_DUR = C["END"]
XF = 0.9                                                   # cross-fade between slides
starts, t = [], 0.0
for _, _, dur in SLIDES:
    starts.append(t); t += dur - XF
END_START = t
TOTAL = END_START + END_DUR
bgs = [load_bg(img, 100 + i) for i, (img, _, _) in enumerate(SLIDES)]
print(f"{len(SLIDES)} slides, total {TOTAL:.1f}s; real photos: {sum(b[1] for b in bgs)}/{len(bgs)}")

def slide_frame(i, ts):
    im, _ = bgs[i]; dur = SLIDES[i][2]
    u = min(max(ts / dur, 0), 1)
    z = (1.0 + 0.07 * u) if i % 2 == 0 else (1.07 - 0.07 * u)   # slow zoom in / out, alternating
    cw, ch = im.width / (1.12 * z) * 1.0, im.height / (1.12 * z)
    cw, ch = W * im.width / (W * 1.12) / z, H * im.height / (H * 1.12) / z
    fx = 0.5 + (0.03 if i % 3 == 0 else -0.03) * u              # tiny lateral drift
    x0 = (im.width - cw) * fx; y0 = (im.height - ch) * 0.45
    fr = im.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    return smog_grade(np.asarray(fr).astype(np.float32))

logo = Image.open(os.path.join(REPO, "assets", "logo_on_dark.png"))
lw = 420
logo_l = np.asarray(logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)).astype(np.float32) / 255

out = P(C.get("OUTPUT", "output/awareness_9x16.mp4")); os.makedirs(os.path.dirname(out), exist_ok=True)

# ---- sound: low city rumble + soft heartbeat (on the heart slides)
beats = []
for i, (_, lines, dur) in enumerate(SLIDES):
    if any("heart" in l.lower() for l, _ in lines):
        tt_ = starts[i] + 0.4
        while tt_ < starts[i] + dur - 0.3:
            beats.append(tt_); tt_ += 0.95
aud = os.path.join(TMP, "sound.wav")
sr = 48000; n = int(TOTAL * sr)
noise = np.random.default_rng(5).standard_normal(n).astype(np.float32)
# brown-ish rumble: integrate + high-pass, slow swells
rum = np.cumsum(noise); rum -= np.convolve(rum, np.ones(4800) / 4800, "same"); rum /= np.abs(rum).max() + 1e-9
tt = np.arange(n) / sr
rum *= (0.55 + 0.25 * np.sin(tt * 0.35) + 0.2 * np.sin(tt * 0.13 + 1)) * 0.22
hb = np.zeros(n, np.float32)
for b in beats:
    for off, amp in ((0.0, 1.0), (0.22, 0.65)):                  # lub-dub
        s0 = int((b + off) * sr); L = int(0.16 * sr)
        if s0 + L < n:
            k = np.arange(L) / sr
            hb[s0:s0 + L] += amp * np.sin(2 * np.pi * 52 * k) * np.exp(-k * 28)
mix = rum + 0.55 * hb
fade = np.minimum(1, np.minimum(tt / 1.0, (TOTAL - tt) / 1.5)); mix *= fade
st = np.stack([mix, mix], 1)
import wave
with wave.open(aud, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes((np.clip(st, -1, 1) * 32767 * 0.8).astype("<i2").tobytes())

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "12M", "-bufsize", "24M",
                        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-20:TP=-2", "-movflags", "+faststart",
                        "-shortest", out], stdin=subprocess.PIPE)
nf = round(TOTAL * FPS)
for fi in range(nf):
    t = fi / FPS
    fr, wsum = np.zeros((H, W, 3), np.float32), 0.0
    for i, (_, lines, dur) in enumerate(SLIDES):
        ts = t - starts[i]
        if -0.01 <= ts < dur:
            wgt = ease(ts / XF) if i else 1.0
            wgt *= 1 - ease((ts - (dur - XF)) / XF) if True else 1
            if wgt > 0:
                fr += slide_frame(i, ts) * wgt; wsum += wgt
    if t >= END_START - XF:
        e = ease((t - END_START + XF) / XF)
        dark = np.full((H, W, 3), 14, np.float32)
        fr = fr * (1 - e) + dark * e if wsum else dark
        wsum = 1
    if wsum:
        fr /= max(wsum, 1.0) if wsum > 1 else 1.0
    hz = haze(t)[..., None]
    fr = fr * (1 - hz) + np.array([196, 186, 166], np.float32) * hz
    fr = fr + particles(t)[..., None] * 70
    # text
    for i, (_, lines, dur) in enumerate(SLIDES):
        ts = t - starts[i]
        if 0 <= ts < dur:
            L = text_layer(lines, ts, dur)
            a = L[..., 3:4]; fr = fr * (1 - a) + L[..., :3] * 255 * a
    if t >= END_START:
        te = t - END_START
        L = text_layer(END_LINES, te, END_DUR + 5)                      # end card does not fade out
        a = L[..., 3:4]; fr = fr * (1 - a) + L[..., :3] * 255 * a
        al = ease((te - 0.9) / 0.8)
        if al > 0:
            lh, lw_ = logo_l.shape[:2]; x0, y0 = (W - lw_) // 2, 1250
            a2 = logo_l[..., 3:4] * al
            roi = fr[y0:y0 + lh, x0:x0 + lw_]; roi[:] = roi * (1 - a2) + logo_l[..., :3] * 255 * a2
    # gentle vignette for focus
    if fi == 0:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        VIG = (1 - 0.30 * (((xx - W / 2) / (W / 1.3)) ** 2 + ((yy - H / 2) / (H / 1.3)) ** 2))[..., None].clip(0.6, 1)
    fr = fr * VIG
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", out)

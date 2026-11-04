#!/usr/bin/env python3
"""Anginax founder reel: cut pauses, grade, caption, brand.

Usage: python3 edit/build.py [--no-captions] [--out output/anginax_reel_9x16.mp4]
Requires: ffmpeg (libx265), numpy, Pillow, Inter font.
Output is HLG HDR (BT.2020), matching the iPhone source colour exactly.
"""
import argparse, json, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from captions import CAPTIONS, DRAMATIC_AFTER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "raw.mp4")
LOGO = os.path.join(ROOT, "assets", "logo_on_dark.png")
FONT_DIR = "/usr/share/fonts/opentype/inter/"
W, H, FPS = 1080, 1920, 30
GOLD = (226, 196, 140)

# ---------------------------------------------------------------- HDR (HLG) helpers
# The source is iPhone HDR (HLG, BT.2020). We keep its pixels untouched and
# deliver HLG HDR, so skin and lighting look exactly as recorded. Overlays are
# designed in sRGB and mapped into HLG with SDR white at HDR reference white
# (203 nits, ~75% HLG signal) per ITU-R BT.2408.
_M709_2020 = np.array([[0.6274, 0.3293, 0.0433],
                       [0.0691, 0.9195, 0.0114],
                       [0.0164, 0.0880, 0.8956]], np.float32)

def srgb_to_hlg(rgb, white=0.203):
    """rgb: float array [..., 3] in 0..1 sRGB -> HLG BT.2020 signal 0..1.
    white: display luminance of sRGB white, as a fraction of 1000 nits."""
    v = np.clip(rgb, 0, 1)
    lin = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    lin = np.clip(lin @ _M709_2020.T, 0, 1)
    e = (lin * white) ** (1 / 1.2)            # inverse OOTF (1000-nit, gamma 1.2)
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    return np.where(e <= 1 / 12, np.sqrt(3 * e), a * np.log(np.maximum(12 * e - b, 1e-6)) + c).astype(np.float32)

def layer_to_hlg(rgba, white=0.203):
    out = rgba.copy()
    out[..., :3] = srgb_to_hlg(rgba[..., :3], white)
    return out

def resize_f(arr, size, box=None, resample=Image.BICUBIC):
    """Resize a float [h, w, c] array channel by channel (keeps 16-bit+ precision)."""
    chans = [np.asarray(Image.fromarray(np.ascontiguousarray(arr[..., i]), "F").resize(size, resample, box=box))
             for i in range(arr.shape[2])]
    return np.stack(chans, axis=-1)

ap = argparse.ArgumentParser()
ap.add_argument("--no-captions", action="store_true")
ap.add_argument("--out", default=os.path.join(ROOT, "output", "anginax_reel_9x16.mp4"))
args = ap.parse_args()
TMP = os.path.join(ROOT, "edit", ".tmp")
os.makedirs(TMP, exist_ok=True)

# ---------------------------------------------------------------- audio analysis
wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav)
a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
HOP = 160  # 10 ms
rms = np.array([20 * np.log10(np.sqrt(np.mean(a[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a), HOP)])
DUR = len(a) / 16000
SIL_DB = -30.0

words = json.load(open(os.path.join(ROOT, "edit", "words.json")))

def quiet_run(t0, t1):
    """Largest run of quiet 10ms frames inside [t0, t1] -> (start, end) or None."""
    i0, i1 = int(t0 * 100), int(t1 * 100)
    best, cur = None, None
    for i in range(i0, min(i1, len(rms))):
        if rms[i] < SIL_DB:
            cur = (cur[0], i + 1) if cur else (i, i + 1)
            if not best or cur[1] - cur[0] > best[1] - best[0]:
                best = cur
        else:
            cur = None
    return (best[0] / 100, best[1] / 100) if best else None

# ---------------------------------------------------------------- segments to keep
START = 1.0   # skip the opening "See," and the pause after it
END = min(DUR, 48.45)
cuts = []     # removed intervals (orig timeline)
for (s0, e0, _), (s1, _, _) in zip(words, words[1:]):
    if s1 < START or s1 - e0 < 0.30:
        continue
    q = quiet_run(e0 - 0.1, s1 + 0.1)
    if not q or q[1] - q[0] < 0.30:
        continue
    keep = 0.42 if any(abs(e0 - d) < 0.05 for d in DRAMATIC_AFTER) else 0.24
    pad_l, pad_r = keep * 0.55, keep * 0.45
    c0, c1 = q[0] + pad_l, q[1] - pad_r
    if c1 - c0 > 0.08:
        cuts.append((c0, c1))

def snap(t):
    return round(t * FPS) / FPS

segs, t = [], START
for c0, c1 in cuts:
    segs.append((snap(t), snap(c0)))
    t = c1
segs.append((snap(t), snap(END)))
segs = [s for s in segs if s[1] - s[0] > 1 / FPS]

def to_new(t_orig):
    acc = 0.0
    for s0, s1 in segs:
        if t_orig < s0:
            return acc
        if t_orig <= s1:
            return acc + t_orig - s0
        acc += s1 - s0
    return acc

BODY = sum(s1 - s0 for s0, s1 in segs)
OUTRO = 2.8          # grey end card with "Learn More"
TOTAL = BODY + OUTRO
print(f"segments: {len(segs)}  body {BODY:.2f}s  total {TOTAL:.2f}s (orig {DUR:.2f}s)")

# ---------------------------------------------------------------- audio edit
fade = 0.012
parts = []
for i, (s0, s1) in enumerate(segs):
    parts.append(f"[0:a]atrim={s0}:{s1},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:d={fade},afade=t=out:st={s1 - s0 - fade}:d={fade}[a{i}]")
graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=0:a=1,apad=whole_dur={TOTAL}[aout]"
audio = os.path.join(TMP, "audio.m4a")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-filter_complex", graph, "-map", "[aout]",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", audio], check=True)

# ---------------------------------------------------------------- caption layers
CAP_SIZE, CAP_LH = 40, 54
CAP_WHITE = 0.60
f_cap = ImageFont.truetype(FONT_DIR + "Inter-Medium.otf", CAP_SIZE)

def render_caption(text):
    tokens, hl = [], False
    for raw in text.split(" "):
        word = raw
        if word.startswith("["):
            hl, word = True, word[1:]
        end_hl = word.endswith("]") or word.endswith("],") or word.endswith("].")
        word = word.replace("]", "")
        tokens.append((word, hl))
        if end_hl:
            hl = False
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    sp = d.textlength(" ", font=f_cap)
    maxw = 1000
    tw = lambda l: d.textlength(" ".join(x for x, _ in l), font=f_cap)
    if tw(tokens) <= maxw:
        lines = [tokens]
    else:
        # two balanced lines; small bonus for breaking right before a highlight
        best = None
        for i in range(1, len(tokens)):
            l0, l1 = tokens[:i], tokens[i:]
            if tw(l0) > maxw or tw(l1) > maxw:
                continue
            score = max(tw(l0), tw(l1)) - (40 if tokens[i][1] and not tokens[i - 1][1] else 0) \
                + (400 if tokens[i][1] and tokens[i - 1][1] else 0)   # never split a highlight
            if best is None or score < best[0]:
                best = (score, [l0, l1])
        lines = best[1]
    LH = CAP_LH
    img = Image.new("RGBA", (W, LH * len(lines) + 30), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ds, dt = ImageDraw.Draw(shadow), ImageDraw.Draw(img)
    layout = []
    for li, line in enumerate(lines):
        x = (W - d.textlength(" ".join(x for x, _ in line), font=f_cap)) / 2
        y = 10 + li * LH
        for j, (word, h) in enumerate(line):
            wl = d.textlength(word, font=f_cap)
            # underline joins across consecutive highlighted words
            ul_end = x + wl + (sp if j + 1 < len(line) and line[j + 1][1] and h else 0)
            layout.append((x, y, word, h, ul_end))
            x += wl + sp
    for x, y, word, h, _ in layout:
        ds.text((x, y + 2), word, font=f_cap, fill=(0, 0, 0, 255))
    # wide soft shadow + tight shadow so white text reads on the white shirt
    wide = shadow.filter(ImageFilter.GaussianBlur(12))
    wide.putalpha(wide.getchannel("A").point(lambda v: min(255, int(v * 1.5))))
    img.alpha_composite(wide)
    tight = shadow.filter(ImageFilter.GaussianBlur(3))
    tight.putalpha(tight.getchannel("A").point(lambda v: int(v * 0.55)))
    img.alpha_composite(tight)
    for x, y, word, h, ul_end in layout:
        dt.text((x, y), word, font=f_cap, fill=GOLD + (255,) if h else (255, 255, 255, 255))
        if h:
            dt.line((x, y + 50, ul_end, y + 50), fill=GOLD + (190,), width=2)
    # captions sit on the white shirt (HLG ~0.80-0.89), so their white is lifted to
    # ~0.92 HLG signal (~600 nits) to read as clean white, not grey
    return layer_to_hlg(np.asarray(img).astype(np.float32) / 255, white=CAP_WHITE)

cap_events = []
if not args.no_captions:
    for i, (t0, t1, text) in enumerate(CAPTIONS):
        n0 = to_new(t0) - 0.05
        n1 = to_new(t1) + 0.25
        if i + 1 < len(CAPTIONS):
            nxt = to_new(CAPTIONS[i + 1][0]) - 0.05
            n1 = nxt if nxt - n1 < 0.45 else n1
        else:
            n1 = BODY + 0.25
        cap_events.append((n0, n1, render_caption(text)))
CAP_Y = 880    # top of caption block: lower neck / collar line


# ---------------------------------------------------------------- b-roll cards
# Slow "swipe" of two proof images over: "And that's the conversation Anginax
# is bringing to global health." Live video stays underneath, blurred + dimmed.
BROLL_IMAGES = [os.path.join(ROOT, "assets", "press_un_article.jpg"),
                os.path.join(ROOT, "assets", "world_heart_summit.jpg")]
BROLL_START = to_new(37.70) - 0.10
BROLL_END = to_new(41.60) + 0.35
print(f"b-roll {BROLL_START:.2f}-{BROLL_END:.2f}s ({BROLL_END - BROLL_START:.2f}s)")

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

def make_card(path, width):
    im = Image.open(path).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    r, pad = 16, 40
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    card = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", card.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + im.width, pad + im.height + 10), r, fill=150)
    card.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))   # soft drop shadow
    inner = im.convert("RGBA"); inner.putalpha(mask)
    card.alpha_composite(inner, (pad, pad))
    return layer_to_hlg(np.asarray(card).astype(np.float32) / 255)

CARDS = [make_card(BROLL_IMAGES[0], 580), make_card(BROLL_IMAGES[1], 960)]
CARD_CY = 480   # vertical centre of cards (above the captions at CAP_Y)
DIM = srgb_to_hlg(np.array([8, 10, 14], np.float32) / 255)

def soft_blur(fr):
    small = resize_f(fr, (W // 6, H // 6), resample=Image.BILINEAR)
    small = resize_f(small, (W // 12, H // 12), resample=Image.BILINEAR)
    return resize_f(small, (W, H), resample=Image.BICUBIC)

def broll(fr, t):
    """fr: float HLG frame [H, W, 3]. Returns composited frame, or None outside window."""
    if not (BROLL_START <= t < BROLL_END):
        return None
    d = BROLL_END - BROLL_START
    u = (t - BROLL_START) / d
    fade_in = ease((t - BROLL_START) / 0.45)
    fade_out = ease((BROLL_END - t) / 0.40)
    bg = soft_blur(fr) * 0.55 + DIM * 0.45
    m = fade_in * fade_out
    base = fr * (1 - m) + bg * m
    swap_mid, swap_len = 0.48, 0.16 * d   # slow swipe between the two cards
    tm = BROLL_START + swap_mid * d
    sw = ease((t - (tm - swap_len / 2)) / swap_len)   # 0 -> card 1, 1 -> card 2
    drift = -60 * u                                    # continuous slow leftward drift
    sc = 1.0 + 0.035 * u                               # very slow push-in
    for i, card in enumerate(CARDS):
        if i == 0:
            alpha, dx = fade_in * (1 - sw), drift - 520 * sw + 50 * (1 - fade_in)
        else:
            alpha, dx = sw * fade_out, drift + 520 * (1 - sw) + 40
        if alpha <= 0.003:
            continue
        ch, cw = card.shape[:2]
        c = resize_f(card, (round(cw * sc), round(ch * sc)))
        over_clip(base, c, (W - c.shape[1]) / 2 + dx, CARD_CY - c.shape[0] / 2, alpha)
    return base

# ---------------------------------------------------------------- logo
logo = Image.open(LOGO)
lw = 150
logo_small = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
logo_small = layer_to_hlg(np.asarray(logo_small).astype(np.float32) / 255)
LOGO_POS = (W - lw - 64, 150)

def over(frame, layer, x, y, alpha=1.0):
    h, w = layer.shape[:2]
    x, y = int(x), int(y)
    roi = frame[y:y + h, x:x + w]
    a = layer[..., 3:4] * alpha
    roi[:] = roi * (1 - a) + layer[..., :3] * a

def over_clip(frame, layer, x, y, alpha=1.0):
    """Like over(), but the layer may extend past the frame edges."""
    x, y = int(x), int(y)
    h, w = layer.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    over(frame[y0:y1, x0:x1], layer[y0 - y:y1 - y, x0 - x:x1 - x], 0, 0, alpha)

# ---------------------------------------------------------------- video
# Pixels stay in the original HLG / BT.2020 signal: no tone-mapping, grading,
# denoise or vignette. Only crop to 9:16, upscale, and a very light sharpen.
vf = ("crop=492:874:7:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.3:5:5:0,"
      "scale=in_color_matrix=bt2020:in_range=tv:out_range=pc,format=rgb48le")
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", vf, "-r", str(FPS),
                        "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                        "-map", "0:v", "-map", "1:a",
                        "-vf", "scale=out_color_matrix=bt2020:in_range=pc:out_range=tv,format=yuv420p10le",
                        "-c:v", "libx265", "-preset", "medium", "-crf", "16", "-tag:v", "hvc1",
                        "-x265-params", "log-level=error:colorprim=bt2020:transfer=arib-std-b67:"
                                        "colormatrix=bt2020nc:range=limited",
                        "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                        "-colorspace", "bt2020nc", "-color_range", "tv",
                        "-c:a", "copy", "-movflags", "+faststart", "-shortest", args.out],
                       stdin=subprocess.PIPE)

ZOOMS = [1.0, 1.075]
FOCUS_Y = 0.30   # keep the face in place when punching in

def zoom(fr, z):
    if z == 1.0:
        return fr
    cw, ch = W / z, H / z
    x0 = (W - cw) / 2
    y0 = (H - ch) * FOCUS_Y
    return resize_f(fr, (W, H), box=(x0, y0, x0 + cw, y0 + ch))

def write(fr):
    enc.stdin.write((np.clip(fr, 0, 1) * 65535 + 0.5).astype("<u2").tobytes())

frame_size = W * H * 3 * 2
src_i, out_t, last = 0, 0.0, None
for k, (s0, s1) in enumerate(segs):
    z = ZOOMS[k % 2]
    f0, f1 = round(s0 * FPS), round(s1 * FPS)
    while src_i < f1:
        buf = dec.stdout.read(frame_size)
        if len(buf) < frame_size:
            break
        if src_i >= f0:
            fr = np.frombuffer(buf, "<u2").reshape(H, W, 3).astype(np.float32) / 65535
            fr = zoom(fr, z)
            t = out_t
            b = broll(fr, t)
            fr = b if b is not None else fr.copy()
            for n0, n1, layer in cap_events:
                if n0 <= t < n1:
                    al = ease((t - n0) / 0.22) * ease((n1 - t) / 0.15)
                    rise = (1 - ease((t - n0) / 0.30)) * 5
                    over(fr, layer, 0, CAP_Y + rise, al)
            over(fr, logo_small, *LOGO_POS, 0.85 * ease(t / 0.6))
            write(fr)
            last = fr
            out_t += 1 / FPS
        src_i += 1

# ---------------------------------------------------------------- outro
# Last frame dissolves into a soft grey background with a highlighted
# "Learn More" call-to-action card in the centre.
def make_cta(text="LEARN MORE"):
    f = ImageFont.truetype(FONT_DIR + "Inter-SemiBold.otf", 38)
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    track = 6
    widths = [d.textlength(ch, font=f) for ch in text]
    tw = sum(widths) + track * (len(text) - 1)
    pw, ph = int(tw + 2 * 70), 104
    pad = 30
    img = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + pw, pad + ph + 8), ph // 2, fill=110)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14)))           # soft shadow
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((pad, pad, pad + pw, pad + ph), ph // 2, fill=(255, 255, 255, 255))
    x = pad + (pw - tw) / 2
    asc, desc = f.getmetrics()
    y = pad + (ph - (asc + desc)) / 2 + 2
    for ch, wd in zip(text, widths):
        dr.text((x, y), ch, font=f, fill=(34, 36, 40, 255))
        x += wd + track
    return layer_to_hlg(np.asarray(img).astype(np.float32) / 255)

cta = make_cta()
GREY = srgb_to_hlg(np.array([0.36, 0.36, 0.37], np.float32))
g = resize_f(resize_f(last, (18, 32), resample=Image.BILINEAR), (W, H), resample=Image.BICUBIC)
lum = (g @ np.array([0.2627, 0.6780, 0.0593], np.float32))[..., None]   # BT.2020 luma
grey_bg = GREY * 0.85 + lum * 0.15        # near-flat grey, faint trace of the curtain light
n_out = round(OUTRO * FPS)
for i in range(n_out):
    t = i / FPS
    m = ease(t / 0.8)
    fr = last * (1 - m) + grey_bg * m
    over(fr, logo_small, *LOGO_POS, 0.85 * (1 - m))
    a = ease((t - 0.7) / 0.6)
    sc = 0.97 + 0.03 * a
    c = resize_f(cta, (round(cta.shape[1] * sc), round(cta.shape[0] * sc)))
    over(fr, c, (W - c.shape[1]) / 2, (H - c.shape[0]) / 2, a)
    write(fr)

enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", args.out)

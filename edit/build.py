#!/usr/bin/env python3
"""Anginax founder reel: cut pauses, grade, caption, brand.

Usage: python3 edit/build.py [--no-captions] [--out output/anginax_reel_9x16.mp4]
Requires: ffmpeg (with zscale/tonemap), numpy, Pillow, Inter font.
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
OUTRO = 2.2
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
        ds.text((x, y + 2), word, font=f_cap, fill=(0, 0, 0, 175))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
    for x, y, word, h, ul_end in layout:
        dt.text((x, y), word, font=f_cap, fill=GOLD + (255,) if h else (255, 255, 255, 255))
        if h:
            dt.line((x, y + 50, ul_end, y + 50), fill=GOLD + (190,), width=2)
    return np.asarray(img).astype(np.float32) / 255

cap_events = []
if not args.no_captions:
    for i, (t0, t1, text) in enumerate(CAPTIONS):
        n0 = to_new(t0) - 0.05
        n1 = to_new(t1) + 0.25
        if i + 1 < len(CAPTIONS):
            nxt = to_new(CAPTIONS[i + 1][0]) - 0.05
            n1 = nxt if nxt - n1 < 0.45 else n1
        else:
            n1 = BODY - 0.1
        cap_events.append((n0, n1, render_caption(text)))
CAP_Y = 1480   # top of caption block; stays above Reels/Ads UI at the bottom

# ---------------------------------------------------------------- logo
logo = Image.open(LOGO)
lw = 150
logo_small = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
logo_small = np.asarray(logo_small).astype(np.float32) / 255
LOGO_POS = (W - lw - 64, 150)
lw2 = 400
logo_big = np.asarray(logo.resize((lw2, round(logo.height * lw2 / logo.width)), Image.LANCZOS)).astype(np.float32) / 255

def over(frame, layer, x, y, alpha=1.0):
    h, w = layer.shape[:2]
    x, y = int(x), int(y)
    roi = frame[y:y + h, x:x + w]
    a = layer[..., 3:4] * alpha
    roi[:] = roi * (1 - a) + layer[..., :3] * a

# ---------------------------------------------------------------- video
vf = ("zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
      "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,hqdn3d=1.5:1.5:4:4,"
      "crop=492:874:7:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.5:5:5:0,"
      "eq=contrast=1.04:saturation=0.92:gamma=0.98,vignette=PI/5,format=rgb24")
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", vf, "-r", str(FPS),
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                        "-profile:v", "high", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                        "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-c:a", "copy", "-movflags", "+faststart", "-shortest", args.out],
                       stdin=subprocess.PIPE)

ZOOMS = [1.0, 1.075]
FOCUS_Y = 0.30   # keep the face in place when punching in

def zoom(img, z):
    if z == 1.0:
        return img
    cw, ch = W / z, H / z
    x0 = (W - cw) / 2
    y0 = (H - ch) * FOCUS_Y
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

frame_size = W * H * 3
src_i, out_t, last = 0, 0.0, None
seg_idx = 0
for k, (s0, s1) in enumerate(segs):
    z = ZOOMS[k % 2]
    f0, f1 = round(s0 * FPS), round(s1 * FPS)
    while src_i < f1:
        buf = dec.stdout.read(frame_size)
        if len(buf) < frame_size:
            break
        if src_i >= f0:
            img = zoom(Image.frombuffer("RGB", (W, H), buf), z)
            fr = np.asarray(img).astype(np.float32) / 255
            t = out_t
            for n0, n1, layer in cap_events:
                if n0 <= t < n1:
                    al = ease((t - n0) / 0.22) * ease((n1 - t) / 0.15)
                    rise = (1 - ease((t - n0) / 0.30)) * 5
                    over(fr, layer, 0, CAP_Y + rise, al)
            over(fr, logo_small, *LOGO_POS, 0.85 * ease(t / 0.6))
            enc.stdin.write((fr * 255 + 0.5).astype(np.uint8).tobytes())
            last = fr
            out_t += 1 / FPS
        src_i += 1

# outro: hold last frame, soften to dark, reveal logo
blur = np.asarray(Image.fromarray((last * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18))).astype(np.float32) / 255
n_out = round(OUTRO * FPS)
for i in range(n_out):
    t = i / FPS
    m = ease((t - 0.35) / 0.7)
    fr = last * (1 - m) + blur * 0.18 * m
    over(fr, logo_small, *LOGO_POS, 0.85 * (1 - m))
    over(fr, logo_big, (W - logo_big.shape[1]) / 2, (H - logo_big.shape[0]) / 2 - 40, ease((t - 0.8) / 0.6))
    enc.stdin.write((np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())

enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", args.out)

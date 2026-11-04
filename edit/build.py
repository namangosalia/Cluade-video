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
OUTRO = 0.9          # frozen last frame while fading to black
FADE_LEN = 1.25      # final fade-out length (starts on live frames)
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
            n1 = BODY + OUTRO
        cap_events.append((n0, n1, render_caption(text)))
CAP_Y = 800    # top of caption block: collar / upper-chest area


# ---------------------------------------------------------------- b-roll cards
# Slow "swipe" of two proof images over: "And that's the conversation Anginax
# is bringing to global health." Live video stays underneath, blurred + dimmed.
BROLL_IMAGES = [os.path.join(ROOT, "assets", "press_un_article.jpg"),
                os.path.join(ROOT, "assets", "world_heart_summit.jpg")]
BROLL_START = to_new(37.70) - 0.10
BROLL_END = to_new(41.60) + 0.35
print(f"b-roll {BROLL_START:.2f}-{BROLL_END:.2f}s ({BROLL_END - BROLL_START:.2f}s)")

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
    return card

CARDS = [make_card(BROLL_IMAGES[0], 580), make_card(BROLL_IMAGES[1], 960)]
CARD_CY = 480   # vertical centre of cards (above the captions at CAP_Y)

def broll(fr_img, t):
    """fr_img: PIL RGB frame. Returns new PIL frame for time t (or None outside window)."""
    if not (BROLL_START <= t < BROLL_END):
        return None
    d = BROLL_END - BROLL_START
    u = (t - BROLL_START) / d
    fade_in = ease((t - BROLL_START) / 0.45)
    fade_out = ease((BROLL_END - t) / 0.40)
    bg_mix = fade_in * fade_out
    small = fr_img.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
    bg = small.resize((W, H), Image.BILINEAR)
    bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 10, 14)), 0.45)
    base = Image.blend(fr_img, bg, bg_mix).convert("RGBA")
    swap_mid, swap_len = 0.48, 0.16 * d   # slow swipe between the two cards
    tm = BROLL_START + swap_mid * d
    sw = ease((t - (tm - swap_len / 2)) / swap_len)   # 0 -> card 1, 1 -> card 2
    drift = -60 * u   # continuous slow leftward drift
    for i, card in enumerate(CARDS):
        if i == 0:
            alpha = fade_in * (1 - sw); dx = drift - 520 * sw
            sc = 1.0 + 0.035 * u
            dx += 50 * (1 - fade_in)
        else:
            alpha = sw * fade_out; dx = drift + 520 * (1 - sw) + 40
            sc = 1.0 + 0.035 * u
        if alpha <= 0.003:
            continue
        cw, ch = round(card.width * sc), round(card.height * sc)
        c = card.resize((cw, ch), Image.BICUBIC)
        if alpha < 1:
            a = c.getchannel("A").point(lambda v, al=alpha: int(v * al))
            c.putalpha(a)
        base.alpha_composite(c, (int((W - cw) / 2 + dx), int(CARD_CY - ch / 2)))
    return base.convert("RGB")

# ---------------------------------------------------------------- logo
logo = Image.open(LOGO)
lw = 150
logo_small = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
logo_small = np.asarray(logo_small).astype(np.float32) / 255
LOGO_POS = (W - lw - 64, 150)

def over(frame, layer, x, y, alpha=1.0):
    h, w = layer.shape[:2]
    x, y = int(x), int(y)
    roi = frame[y:y + h, x:x + w]
    a = layer[..., 3:4] * alpha
    roi[:] = roi * (1 - a) + layer[..., :3] * a

# ---------------------------------------------------------------- video
# Keep the original lighting: HLG signal kept as-is, only BT.2020 -> BT.709 colour
# primaries converted (no tone-mapping, grading or vignette).
vf = ("zscale=tin=bt709:t=bt709:pin=bt2020:p=bt709:min=bt2020nc:m=bt709:rin=tv:r=tv,"
      "format=yuv420p,hqdn3d=1.5:1.5:4:4,"
      "crop=492:874:7:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.5:5:5:0,format=rgb24")
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
            t = out_t
            img = broll(img, t) or img
            fr = np.asarray(img).astype(np.float32) / 255
            for n0, n1, layer in cap_events:
                if n0 <= t < n1:
                    al = ease((t - n0) / 0.22) * ease((n1 - t) / 0.15)
                    rise = (1 - ease((t - n0) / 0.30)) * 5
                    over(fr, layer, 0, CAP_Y + rise, al)
            over(fr, logo_small, *LOGO_POS, 0.85 * ease(t / 0.6))
            last = fr.copy()
            fr *= ease((TOTAL - t) / FADE_LEN)
            enc.stdin.write((fr * 255 + 0.5).astype(np.uint8).tobytes())
            out_t += 1 / FPS
        src_i += 1

# outro: hold the last frame (captions + logo included) and finish the fade to black
n_out = round(OUTRO * FPS)
for i in range(n_out):
    t = out_t + i / FPS
    fr = last * ease((TOTAL - t) / FADE_LEN)
    enc.stdin.write((np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())

enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", args.out)

#!/usr/bin/env python3
"""Anginax founder reel: cut pauses, grade, caption, brand.

Usage: python3 edit/build.py [--no-captions] [--out output/anginax_reel_9x16.mp4]
Requires: ffmpeg (libx265), numpy, Pillow, Inter font.
Output is HLG HDR (BT.2020), matching the iPhone source colour exactly.
"""
import argparse, json, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from captions import GROUPS, STATEMENTS, DRAMATIC_AFTER
import chart_plate
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video2", "edit"))
import trailer_text as tt   # same typography system as video 2

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

# ---------------------------------------------------------------- studio voice
# The lav mic sounds muffled (3-6 kHz sits ~40 dB under the mids). Broadcast-style
# chain, applied to the continuous recording before cutting so dynamics stay natural.
VOICE_CHAIN = ",".join([
    "highpass=f=70:poles=2",                         # rumble / handling noise
    "afftdn=nr=8:nf=-48:tn=1",                       # light broadband denoise
    "equalizer=f=130:t=q:w=0.9:g=1.5",               # chest warmth
    "equalizer=f=520:t=q:w=1.1:g=-3",                # less boxy
    "equalizer=f=2900:t=q:w=0.9:g=6",                # presence / intelligibility
    "equalizer=f=5200:t=q:w=1.0:g=6",                # clarity
    "highshelf=f=9000:g=2",                          # a touch of air
    "deesser=i=0.4:m=0.5:f=0.5",                     # tame boosted sibilance
    "acompressor=threshold=-21dB:ratio=3:attack=6:release=140:knee=4:makeup=2",
    "alimiter=limit=0.89:attack=3:release=60:level=disabled",
])
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-vn", "-af", VOICE_CHAIN, "-ac", "1",
                      "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
v = np.frombuffer(raw, "<f4").copy()
# Duck the pauses between phrases by ~15 dB (room tone + music bed). Only stretches
# that were measurably quiet in the original (< -30 dB) are touched, with margins
# and 50 ms ramps, so word starts and tails stay intact.
env = np.ones(len(v), np.float32)
DUCK, RAMP = 10 ** (-15 / 20), 0.05
for (s0, e0, _), (s1, _, _) in zip(words, words[1:]):
    q = quiet_run(e0 - 0.1, s1 + 0.1)
    if not q or q[1] - q[0] < 0.2:
        continue
    a0 = max(q[0], e0) + 0.14      # leave soft word endings ("-ing", "-al") untouched
    a1 = min(q[1], s1) - 0.07      # and breaths / onsets before the next word
    if a1 - a0 < 2 * RAMP:
        continue
    i0, i1, r = int(a0 * 48000), int(a1 * 48000), int(RAMP * 48000)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r))
    env[i0:i0 + r] = np.minimum(env[i0:i0 + r], 1 - (1 - DUCK) * ramp)
    env[i0 + r:i1 - r] = np.minimum(env[i0 + r:i1 - r], DUCK)
    env[i1 - r:i1] = np.minimum(env[i1 - r:i1], DUCK + (1 - DUCK) * ramp)
v *= env
voice = os.path.join(TMP, "voice.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", "48000", "-ac", "1", "-i", "-",
                "-ac", "2", "-c:a", "pcm_s24le", voice], input=v.tobytes(), check=True)

# ---------------------------------------------------------------- audio edit
fade = 0.012
parts = []
for i, (s0, s1) in enumerate(segs):
    parts.append(f"[0:a]atrim={s0}:{s1},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:d={fade},afade=t=out:st={s1 - s0 - fade}:d={fade}[a{i}]")
graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=0:a=1,apad=whole_dur={TOTAL}[aout]"
cut = os.path.join(TMP, "cut.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", voice, "-filter_complex", graph, "-map", "[aout]",
                "-c:a", "pcm_s24le", cut], check=True)
# two-pass loudness normalisation: -14 LUFS integrated, -1 dBTP (Instagram / Meta)
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", cut, "-af",
                       "loudnorm=I=-14:TP=-1:LRA=7:print_format=json", "-f", "null", "-"],
                      capture_output=True, text=True).stderr
m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1:LRA=7:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
audio = os.path.join(TMP, "audio.m4a")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cut, "-af", ln, "-ar", "48000",
                "-c:a", "aac", "-b:a", "256k", audio], check=True)

# ---------------------------------------------------------------- trailer typography (as video 2)
cap_groups = tt.build_groups(GROUPS, words, to_new, BODY)
statements = tt.build_statements(STATEMENTS, words, to_new)
for st in statements:
    print(f"statement {st.t0:6.2f}-{st.t1:6.2f}s")

def gray_amount(t):
    g = 0.0
    for st in statements:
        a_, b_ = st.t0 - 0.25, st.t1
        if a_ <= t < b_ + 0.5:
            g = max(g, ease((t - a_) / 0.5) * (1 - ease((t - b_) / 0.5)))
    return g

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
    im = (Image.open(path) if isinstance(path, str) else path).convert("RGB")
    target = (width, round(im.height * width / im.width))
    if width > im.width * 1.3:   # low-res source: upscale in two steps, then crisp up the text
        mid = (round((im.width + width) / 2), round((im.height + target[1]) / 2))
        im = im.resize(mid, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=1))
    im = im.resize(target, Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))
    r, pad = 16, 40
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    card = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", card.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + im.width, pad + im.height + 10), r, fill=150)
    card.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))   # soft drop shadow
    inner = im.convert("RGBA"); inner.putalpha(mask)
    card.alpha_composite(inner, (pad, pad))
    # brighter than reference white so photos read clean next to the HDR video
    return layer_to_hlg(np.asarray(card).astype(np.float32) / 255, white=CARD_WHITE)

CARD_WHITE = 0.45
CARDS = [make_card(BROLL_IMAGES[0], 680), make_card(BROLL_IMAGES[1], 1000)]
CARD_CY = 455   # vertical centre of cards (above the captions at CAP_Y)
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


# ---------------------------------------------------------------- animated risk chart
# Over "knowing your risk ... at your home": the Longitudinal Care infographic as a
# static card; only its risk curve draws itself from High to Low risk, in step with
# the words, with each risk pill fading in as the line reaches its marker.
IG_PATH = os.path.join(ROOT, "assets", "longitudinal_chart.png")
IG_W = 1000
ig_orig, ig_clean, ig_curve = chart_plate.build(IG_PATH)
IG_CARD_ORIG = make_card(Image.fromarray((ig_orig * 255).astype(np.uint8)), IG_W)
IG_CARD_CLEAN = make_card(Image.fromarray((ig_clean * 255 + 0.5).astype(np.uint8)), IG_W)
IG_SC = IG_W / ig_orig.shape[1]
IG_PAD = 40
IG_CY = 470
IG_START = to_new(16.62) - 0.40
IG_END = to_new(27.14) + 0.40
# curve tip position (image px) at word times (original timeline)
IG_KEYS = [(16.70, chart_plate.PX0), (17.30, chart_plate.DOTS_X[0]), (18.55, chart_plate.DOTS_X[1]),
           (19.45, chart_plate.DOTS_X[2]), (22.30, 1612)]
IG_KEYS = [(to_new(t), x) for t, x in IG_KEYS]
print(f"risk chart {IG_START:.2f}-{IG_END:.2f}s")

def ig_tip(t):
    if t <= IG_KEYS[0][0]:
        return IG_KEYS[0][1]
    for (t0, x0), (t1, x1) in zip(IG_KEYS, IG_KEYS[1:]):
        if t < t1:
            u = (t - t0) / (t1 - t0)
            u = 0.5 * u + 0.5 * ease(u)          # gentle settle at each milestone
            return x0 + (x1 - x0) * u
    return IG_KEYS[-1][1]

_ch, _cw = IG_CARD_ORIG.shape[:2]
_xs = (np.arange(_cw) - IG_PAD) / IG_SC        # card column -> image x
_pill_alpha_mask = []
for (x0, y0, x1, y1) in chart_plate.PILLS:
    m = np.zeros((_ch, _cw), np.float32)
    m[int(y0 * IG_SC) + IG_PAD:int(y1 * IG_SC) + IG_PAD + 1, int(x0 * IG_SC) + IG_PAD:int(x1 * IG_SC) + IG_PAD + 1] = 1
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32) / 255
    _pill_alpha_mask.append(m)
_pill_any = np.clip(sum(_pill_alpha_mask), 0, 1)
_glow_col = srgb_to_hlg(np.array([1.0, 1.0, 1.0], np.float32), white=CARD_WHITE)

# Gentle push-in on the chart while the curve draws, then ease back out to the
# full graphic. The card frame stays put; only the picture inside it moves.
IG_ZOOM = 1.30
IG_FOCUS = (1175, 430)        # chart panel centre (image px)
_iw, _ih = _cw - 2 * IG_PAD, _ch - 2 * IG_PAD
_inner = Image.new("L", (_cw, _ch), 0)
ImageDraw.Draw(_inner).rounded_rectangle((IG_PAD, IG_PAD, IG_PAD + _iw - 1, IG_PAD + _ih - 1), 16, fill=255)
_inner = (np.asarray(_inner).astype(np.float32) / 255)[IG_PAD:IG_PAD + _ih, IG_PAD:IG_PAD + _iw, None]

def ig_zoom(t):
    """(zoom, focus_x, focus_y) in image px."""
    t_in0, t_in1 = IG_KEYS[0][0] - 0.15, IG_KEYS[0][0] + 1.4      # push in as the line starts
    t_out0, t_out1 = IG_KEYS[-1][0] + 0.2, IG_KEYS[-1][0] + 1.8   # ease out after "over time"
    k = ease((t - t_in0) / (t_in1 - t_in0)) * (1 - ease((t - t_out0) / (t_out1 - t_out0)))
    z = 1 + (IG_ZOOM - 1) * k
    tip = ig_tip(t)
    fx = IG_FOCUS[0] + 0.18 * (tip - IG_FOCUS[0])                  # drift slightly with the line
    fy = IG_FOCUS[1]
    cx0, cy0 = ig_orig.shape[1] / 2, ig_orig.shape[0] / 2
    return z, cx0 + (fx - cx0) * k, cy0 + (fy - cy0) * k

def apply_zoom(card, t):
    z, fx, fy = ig_zoom(t)
    if z <= 1.0005:
        return card
    inner = card[IG_PAD:IG_PAD + _ih, IG_PAD:IG_PAD + _iw, :3]
    bw, bh = _iw / z, _ih / z
    cx, cy = fx * IG_SC, fy * IG_SC
    x0 = min(max(cx - bw / 2, 0), _iw - bw)
    y0 = min(max(cy - bh / 2, 0), _ih - bh)
    zoomed = resize_f(inner, (_iw, _ih), box=(x0, y0, x0 + bw, y0 + bh))
    out = card.copy()
    out[IG_PAD:IG_PAD + _ih, IG_PAD:IG_PAD + _iw, :3] = zoomed * _inner + inner * (1 - _inner)
    return out

def ig_card(t):
    tip = ig_tip(t)
    reveal = np.clip((tip - _xs) / 10 + 0.5, 0, 1)[None, :] * np.ones((_ch, 1), np.float32)
    mask = reveal * (1 - _pill_any)
    for k, pm in enumerate(_pill_alpha_mask):
        tk = next(tt for tt, xx in IG_KEYS if xx == chart_plate.DOTS_X[k])
        mask += pm * ease((t - tk + 0.05) / 0.45)
    card = IG_CARD_CLEAN.copy()
    card[..., :3] = IG_CARD_CLEAN[..., :3] * (1 - mask[..., None]) + IG_CARD_ORIG[..., :3] * mask[..., None]
    # soft glow leading the line while it draws
    g = 1 - ease((t - IG_KEYS[-1][0]) / 0.5)
    if g > 0 and t > IG_KEYS[0][0]:
        cx = tip * IG_SC + IG_PAD
        cy = ig_curve[int(min(max(tip, 0), len(ig_curve) - 1))] * IG_SC + IG_PAD
        r = 26
        y0, y1, x0, x1 = int(cy - r), int(cy + r), int(cx - r), int(cx + r)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        a = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 7.0 ** 2)) * 0.85 * g
        sub = card[y0:y1, x0:x1, :3]
        sub[:] = sub * (1 - a[..., None]) + _glow_col * a[..., None]
    return apply_zoom(card, t)

def infographic(fr, t):
    if not (IG_START <= t < IG_END):
        return None
    fade_in = ease((t - IG_START) / 0.45)
    fade_out = ease((IG_END - t) / 0.40)
    m = fade_in * fade_out
    bg = soft_blur(fr) * 0.55 + DIM * 0.45
    base = fr * (1 - m) + bg * m
    c = ig_card(t)
    over_clip(base, c, (W - c.shape[1]) / 2, IG_CY - c.shape[0] / 2, m)
    return base

# ---------------------------------------------------------------- logo
logo = Image.open(LOGO)
lw = 175
logo_small = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
logo_small = np.asarray(logo_small).astype(np.float32) / 255
logo_small[..., 3] = np.clip(logo_small[..., 3] * 1.25, 0, 1)   # firmer edges on thin strokes
logo_small = layer_to_hlg(logo_small, white=0.60)
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

FRAMES = [(1.00, 1.05), (1.20, 1.15), (1.08, 1.13), (1.26, 1.20), (1.04, 1.00), (1.14, 1.20)]
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
    z0, z1 = FRAMES[k % len(FRAMES)]
    f0, f1 = round(s0 * FPS), round(s1 * FPS)
    while src_i < f1:
        buf = dec.stdout.read(frame_size)
        if len(buf) < frame_size:
            break
        if src_i >= f0:
            fr = np.frombuffer(buf, "<u2").reshape(H, W, 3).astype(np.float32) / 65535
            fr = zoom(fr, z0 + (z1 - z0) * ease((src_i - f0) / max(f1 - f0, 1)))
            t = out_t
            b = broll(fr, t)
            if b is None:
                b = infographic(fr, t)
            fr = b if b is not None else fr.copy()
            g = gray_amount(t)
            if g > 0:
                Y = (fr @ np.array([0.2627, 0.6780, 0.0593], np.float32))[..., None]
                fr = (fr * (1 - 0.90 * g) + Y * 0.90 * g) * (1 - 0.50 * g)
            for st in statements:
                lay = st.render(t)
                if lay:
                    over_clip(fr, lay[0], lay[1], lay[2])
            for grp in (cap_groups if g < 0.25 else ()):     # captions give way to statements
                lay = grp.render(t)
                if lay:
                    over_clip(fr, lay[0], lay[1], lay[2])
            # logo steps aside while the photo cards are on screen
            hide = ease((t - BROLL_START) / 0.4) * ease((BROLL_END - t) / 0.4) if BROLL_START <= t < BROLL_END else 0
            if IG_START <= t < IG_END:
                hide = ease((t - IG_START) / 0.4) * ease((IG_END - t) / 0.4)
            over(fr, logo_small, *LOGO_POS, ease(t / 0.6) * (1 - hide))
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
    over(fr, logo_small, *LOGO_POS, 1 - m)
    a = ease((t - 0.7) / 0.6)
    sc = 0.97 + 0.03 * a
    c = resize_f(cta, (round(cta.shape[1] * sc), round(cta.shape[0] * sc)))
    over(fr, c, (W - c.shape[1]) / 2, (H - c.shape[0]) / 2, a)
    write(fr)

enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", args.out)

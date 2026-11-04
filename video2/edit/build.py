#!/usr/bin/env python3
"""Anginax reel #2 - 'Why don't we prevent it?'

Cuts pauses, studio voice, keeps the iPhone HDR colour, captions with highlighted
numbers, motion-graphic cutaways (voice continues underneath), Learn More end card.

Usage: python3 video2/edit/build.py [--out video2/output/anginax_why_prevention_9x16.mp4]
"""
import argparse, json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from captions import GROUPS, STATEMENTS, DRAMATIC_AFTER
import trailer_text as tt
import cine
import flow

ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
SRC = os.path.join(ROOT, "source", "raw.mp4")
LOGO = os.path.join(REPO, "assets", "logo_on_dark.png")
FONT_DIR = "/usr/share/fonts/opentype/inter/"
W, H, FPS = 1080, 1920, 30
GOLD = (226, 196, 140)

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join(ROOT, "output", "anginax_why_prevention_9x16.mp4"))
args = ap.parse_args()
TMP = os.path.join(HERE, ".tmp")
os.makedirs(TMP, exist_ok=True)

# ---------------------------------------------------------------- HDR (HLG) helpers
_M709_2020 = np.array([[0.6274, 0.3293, 0.0433],
                       [0.0691, 0.9195, 0.0114],
                       [0.0164, 0.0880, 0.8956]], np.float32)

def srgb_to_hlg(rgb, white=0.203):
    v = np.clip(rgb, 0, 1)
    lin = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    lin = np.clip(lin @ _M709_2020.T, 0, 1)
    e = (lin * white) ** (1 / 1.2)
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    return np.where(e <= 1 / 12, np.sqrt(3 * e), a * np.log(np.maximum(12 * e - b, 1e-6)) + c).astype(np.float32)

def layer_to_hlg(rgba, white=0.203):
    out = rgba.copy()
    out[..., :3] = srgb_to_hlg(rgba[..., :3], white)
    return out

def resize_f(arr, size, box=None, resample=Image.BICUBIC):
    chans = [np.asarray(Image.fromarray(np.ascontiguousarray(arr[..., i]), "F").resize(size, resample, box=box))
             for i in range(arr.shape[2])]
    return np.stack(chans, axis=-1)

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

def over(frame, layer, x, y, alpha=1.0):
    h, w = layer.shape[:2]
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    l = layer[y0 - y:y1 - y, x0 - x:x1 - x]
    roi = frame[y0:y1, x0:x1]
    a = l[..., 3:4] * alpha
    roi[:] = roi * (1 - a) + l[..., :3] * a

# ---------------------------------------------------------------- audio analysis + cuts
# Part 1 + the continuation ("This is neither practical nor convenient... Then what do we do?")
SRC1, SRC2 = SRC, os.path.join(ROOT, "source", "raw_part2.mp4")
lst = os.path.join(TMP, "concat.txt")
open(lst, "w").write(f"file '{SRC1}'\nfile '{SRC2}'\n")
SRC = os.path.join(TMP, "combined.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", SRC], check=True)
OFFSET = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                               "-of", "csv=p=0", SRC1], capture_output=True, text=True).stdout.strip())

wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav)
a16 = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
DUR = len(a16) / 16000
words = json.load(open(os.path.join(HERE, "words.json")))
words += [[s_ + OFFSET, e_ + OFFSET, t_] for s_, e_, t_ in json.load(open(os.path.join(HERE, "words_part2.json")))]

# every quiet stretch (< -30 dB, >= 0.30 s), wherever it falls (also inside long word spans)
runs, s = [], None
for i, q in enumerate(rms < -30.0):
    if q and s is None:
        s = i
    if not q and s is not None:
        if i - s >= 30:
            runs.append((s / 100, i / 100))
        s = None

START, END = 0.62, min(DUR, OFFSET + 5.88 + 0.45)
cuts = []
for q0, q1 in runs:
    if q0 < START or q1 > END:
        continue
    keep = 0.62 if any(abs(q0 - d) < 0.08 for d in DRAMATIC_AFTER) else 0.30
    if q0 < OFFSET < q1:
        keep = 0.70                                     # breath before the continuation
    c0, c1 = q0 + keep * 0.55, q1 - keep * 0.45
    if c1 - c0 > 0.08:
        cuts.append((c0, c1))

snap = lambda t: round(t * FPS) / FPS
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
OUTRO = 2.8
TOTAL = BODY + OUTRO
print(f"segments: {len(segs)}  body {BODY:.2f}s  total {TOTAL:.2f}s (orig {DUR:.2f}s)")

# ---------------------------------------------------------------- studio voice + audio edit
VOICE_CHAIN = ",".join([
    "highpass=f=70:poles=2", "afftdn=nr=8:nf=-48:tn=1",
    "equalizer=f=130:t=q:w=0.9:g=1.5", "equalizer=f=520:t=q:w=1.1:g=-3",
    "equalizer=f=2900:t=q:w=0.9:g=6", "equalizer=f=5200:t=q:w=1.0:g=6", "highshelf=f=9000:g=2",
    "deesser=i=0.4:m=0.5:f=0.5",
    "acompressor=threshold=-21dB:ratio=3:attack=6:release=140:knee=4:makeup=2",
    "alimiter=limit=0.89:attack=3:release=60:level=disabled",
])
voice = os.path.join(TMP, "voice.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-vn", "-af", VOICE_CHAIN, "-ac", "2",
                "-ar", "48000", "-c:a", "pcm_s24le", voice], check=True)
fade = 0.012
parts = [f"[0:a]atrim={s0}:{s1},asetpts=PTS-STARTPTS,afade=t=in:d={fade},"
         f"afade=t=out:st={s1 - s0 - fade}:d={fade}[a{i}]" for i, (s0, s1) in enumerate(segs)]
graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=0:a=1,apad=whole_dur={TOTAL}[aout]"
cut = os.path.join(TMP, "cut.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", voice, "-filter_complex", graph, "-map", "[aout]",
                "-c:a", "pcm_s24le", cut], check=True)
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", cut, "-af", "loudnorm=I=-14:TP=-1:LRA=7:print_format=json",
                       "-f", "null", "-"], capture_output=True, text=True).stderr
m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1:LRA=7:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
audio = os.path.join(TMP, "audio.m4a")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cut, "-af", ln, "-ar", "48000", "-c:a", "aac",
                "-b:a", "256k", audio], check=True)

# ---------------------------------------------------------------- trailer typography
cap_groups = tt.build_groups(GROUPS, words, to_new, BODY)
statements = tt.build_statements(STATEMENTS, words, to_new)
for st in statements:
    print(f"statement {st.kind:8s} {st.t0:6.2f}-{st.t1:6.2f}s")

# ---------------------------------------------------------------- cutaway scenes
def window(o0, o1, lead=0.15, tail=0.12):
    return to_new(o0) - lead, to_new(o1) - tail

def rel(o, start):
    return to_new(o) - start

# Naman stays on screen for almost the whole video. One cutaway sequence (flow.py)
# shows a person going through the effort of prevention, shot by shot, on his words.
SCENES = []
_shots = [(37.10, flow.Phone), (38.58, flow.Hospital), (40.22, flow.Queue), (42.04, flow.BusyLobby), (43.32, flow.Payment)]
_end = to_new(45.66) - 0.10
for i, (o, cls) in enumerate(_shots):
    a_ = to_new(o) - 0.30
    b_ = (to_new(_shots[i + 1][0]) - 0.30 + 0.45) if i + 1 < len(_shots) else _end
    SCENES.append((a_, b_, cls(b_ - a_)))
for a_, b_, fn in SCENES:
    print(f"shot  {type(fn).__name__:10s} {a_:6.2f}-{b_:6.2f}s")

# Statement moments: Naman greys out and dims behind full-screen type.
def gray_amount(t):
    g = 0.0
    for st in statements:
        a_, b_ = st.t0 - 0.25, st.t1
        if a_ <= t < b_ + 0.5:
            g = max(g, ease((t - a_) / 0.5) * (1 - ease((t - b_) / 0.5)))
    return g

DISSOLVE = 0.45

# ---------------------------------------------------------------- logo
logo = Image.open(LOGO)
lw = 175
logo_small = np.asarray(logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)).astype(np.float32) / 255
logo_small[..., 3] = np.clip(logo_small[..., 3] * 1.25, 0, 1)
logo_small = layer_to_hlg(logo_small, white=0.60)
LOGO_POS = (W - lw - 64, 150)

# ---------------------------------------------------------------- video
vf = ("crop=492:874:7:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.3:5:5:0,"
      "scale=in_color_matrix=bt2020:in_range=tv:out_range=pc,format=rgb48le")
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", vf, "-r", str(FPS),
                        "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], stdout=subprocess.PIPE)
os.makedirs(os.path.dirname(args.out), exist_ok=True)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
                        "-vf", "scale=out_color_matrix=bt2020:in_range=pc:out_range=tv,format=yuv420p10le",
                        "-c:v", "libx265", "-preset", "medium", "-crf", "16", "-tag:v", "hvc1",
                        "-x265-params", "log-level=error:colorprim=bt2020:transfer=arib-std-b67:"
                                        "colormatrix=bt2020nc:range=limited",
                        "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                        "-colorspace", "bt2020nc", "-color_range", "tv",
                        "-c:a", "copy", "-movflags", "+faststart", "-shortest", args.out],
                       stdin=subprocess.PIPE)

FOCUS_Y = 0.30
# (start, end) zoom per cut: wide, push-in close, medium pull-out, tight
FRAMES = [(1.00, 1.05), (1.20, 1.15), (1.08, 1.13), (1.26, 1.20), (1.04, 1.00), (1.14, 1.20)]
PUSH_FROM = to_new(52.79)          # slow push-in through the closing question
PUSH_TO = to_new(63.26) + 0.3

def zoom(fr, z):
    if z <= 1.0005:
        return fr
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) * FOCUS_Y
    return resize_f(fr, (W, H), box=(x0, y0, x0 + cw, y0 + ch))

def write(fr):
    enc.stdin.write((np.clip(fr, 0, 1) * 65535 + 0.5).astype("<u2").tobytes())

frame_size = W * H * 3 * 2
src_i, out_t, last = 0, 0.0, None
for k, (s0, s1) in enumerate(segs):
    f0, f1 = round(s0 * FPS), round(s1 * FPS)
    while src_i < f1:
        buf = dec.stdout.read(frame_size)
        if len(buf) < frame_size:
            break
        if src_i >= f0:
            t = out_t
            fr = np.frombuffer(buf, "<u2").reshape(H, W, 3).astype(np.float32) / 65535
            if PUSH_FROM <= t < PUSH_TO:
                z = 1.04 + 0.14 * ease((t - PUSH_FROM) / (PUSH_TO - PUSH_FROM))
            else:
                z0, z1 = FRAMES[k % len(FRAMES)]
                z = z0 + (z1 - z0) * ease((src_i - f0) / max(f1 - f0, 1))
            fr = zoom(fr, z)
            # cross-dissolve: speaker <-> cutaways (and cutaway <-> cutaway where they overlap)
            act = []
            for a_, b_, fn in SCENES:
                if a_ <= t < b_:
                    wgt = (1.0 if a_ <= 0 else ease((t - a_) / DISSOLVE)) * ease((b_ - t) / DISSOLVE)
                    act.append((wgt, fn(t - a_)))
            if act:
                tot = sum(wg for wg, _ in act)
                mix = min(tot, 1.0)
                g = sum(wg * f_ for wg, f_ in act) / tot
                fr = fr * (1 - mix) + g * mix
            g = gray_amount(t)
            if g > 0:
                Y = (fr @ np.array([0.2627, 0.6780, 0.0593], np.float32))[..., None]
                fr = (fr * (1 - 0.90 * g) + Y * 0.90 * g) * (1 - 0.50 * g)
            for st in statements:
                lay = st.render(t)
                if lay:
                    over(fr, *lay)
            for grp in (cap_groups if g < 0.25 else ()):     # captions give way to statements
                lay = grp.render(t)
                if lay:
                    over(fr, *lay)
            over(fr, logo_small, *LOGO_POS, ease(t / 0.6))
            write(fr)
            last = fr
            out_t += 1 / FPS
        src_i += 1

# ---------------------------------------------------------------- outro: grey + Learn More
def make_cta(text="LEARN MORE"):
    f = ImageFont.truetype(FONT_DIR + "Inter-SemiBold.otf", 38)
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    track = 6
    widths = [d.textlength(ch, font=f) for ch in text]
    tw = sum(widths) + track * (len(text) - 1)
    pw, ph, pad = int(tw + 2 * 70), 104, 30
    img = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + pw, pad + ph + 8), ph // 2, fill=110)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14)))
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
lum = (g @ np.array([0.2627, 0.6780, 0.0593], np.float32))[..., None]
grey_bg = GREY * 0.85 + lum * 0.15
for i in range(round(OUTRO * FPS)):
    t = i / FPS
    mm = ease(t / 0.8)
    fr = last * (1 - mm) + grey_bg * mm
    over(fr, logo_small, *LOGO_POS, 1 - mm)
    a = ease((t - 0.7) / 0.6)
    sc_ = 0.97 + 0.03 * a
    c = resize_f(cta, (round(cta.shape[1] * sc_), round(cta.shape[0] * sc_)))
    over(fr, c, (W - c.shape[1]) / 2, (H - c.shape[0]) / 2, a)
    write(fr)

enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", args.out)

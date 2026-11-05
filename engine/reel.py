#!/usr/bin/env python3
"""Anginax reel engine: raw iPhone selfie video(s) -> finished 9:16 HDR reel in the house style.

    python3 engine/reel.py videos/<slug>/config.py [--out path.mp4]

The config (see videos/_template/config.py) lists the sources and the editorial
choices: caption groups, full-screen statements, cutaways. Everything else is the
house style agreed for the first two reels (see MASTER_PROMPT.md):
pause cutting, studio voice, untouched HDR colour, varied framing, Anton captions,
greyed-out statements, cutaways, small logo, grey 'Learn More' end card.
"""
import argparse, json, os, runpy, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
sys.path.insert(0, ENGINE)
import trailer_text as tt
import cine
import flow

ap = argparse.ArgumentParser()
ap.add_argument("config")
ap.add_argument("--out")
args = ap.parse_args()
CFG_PATH = os.path.abspath(args.config)
VDIR = os.path.dirname(CFG_PATH)
C = runpy.run_path(CFG_PATH)
P = lambda p: p if os.path.isabs(p) else os.path.join(VDIR, p)

SOURCES = [P(s) for s in C["SOURCES"]]
OUT = os.path.abspath(args.out) if args.out else P(C.get("OUTPUT", "output/reel_9x16.mp4"))
GROUPS, STATEMENTS = C.get("GROUPS", []), C.get("STATEMENTS", [])
CUTAWAYS = C.get("CUTAWAYS", [])
tt.set_accent(C.get("ACCENT", "red"))
LOGO = os.path.join(REPO, "assets", "logo_on_dark.png")
FONT_DIR = "/usr/share/fonts/opentype/inter/"
W, H, FPS = 1080, 1920, 30
TMP = os.path.join(VDIR, ".tmp")
os.makedirs(TMP, exist_ok=True)

# ---------------------------------------------------------------- helpers
srgb_to_hlg = cine.srgb_to_hlg

def layer_to_hlg(rgba, white=0.203):
    out = rgba.copy()
    out[..., :3] = srgb_to_hlg(rgba[..., :3], white)
    return out

def resize_f(arr, size, box=None, resample=Image.BICUBIC):
    chans = [np.asarray(Image.fromarray(np.ascontiguousarray(arr[..., i]), "F").resize(size, resample, box=box))
             for i in range(arr.shape[2])]
    return np.stack(chans, axis=-1)

ease = cine.ease

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

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)

def probe(path, entries, stream="v:0"):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", entries,
                          "-of", "default=nw=1", path], capture_output=True, text=True).stdout
    return dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)

# ---------------------------------------------------------------- sources -> one recording
if len(SOURCES) > 1:
    lst = os.path.join(TMP, "concat.txt")
    open(lst, "w").write("".join(f"file '{s}'\n" for s in SOURCES))
    SRC = os.path.join(TMP, "combined.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", SRC])
else:
    SRC = SOURCES[0]
OFFSETS, acc = [], 0.0
for s_ in SOURCES:
    OFFSETS.append(acc)
    acc += float(probe(s_, "stream=duration")["duration"])
vinfo = probe(SOURCES[0], "stream=width,height,color_transfer")
SRC_W, SRC_H = int(vinfo["width"]), int(vinfo["height"])
HDR_SRC = vinfo.get("color_transfer") == "arib-std-b67"

words = json.load(open(P(C.get("WORDS", "words.json"))))

# ---------------------------------------------------------------- pauses -> cuts
wav = os.path.join(TMP, "a.wav")
run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "16000", wav])
wv = wave.open(wav)
a16 = np.frombuffer(wv.readframes(wv.getnframes()), np.int16).astype(np.float32) / 32768
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
DUR = len(a16) / 16000
runs, s_ = [], None
for i, q in enumerate(rms < -30.0):
    if q and s_ is None:
        s_ = i
    if not q and s_ is not None:
        if i - s_ >= 30:
            runs.append((s_ / 100, i / 100))
        s_ = None

first = C.get("START_WORD", 0)
START = max(0.0, words[first][0] - 0.08) if first else 0.0
# whisper often stamps the first word at 0.0 although speech starts later: trust the audio
lead = next((b for a, b in runs if a <= START + 0.05 and b > START), None)
if lead:
    START = max(START, lead - 0.08)
END = min(DUR, words[C.get("END_WORD", len(words) - 1)][1] + 0.45)
dramatic_words = set(C.get("DRAMATIC_AFTER_WORDS", []))
for i, (_, _, t_) in enumerate(words):              # default: longer breath after every sentence end
    if C.get("AUTO_DRAMATIC", True) and t_.strip().endswith(("?", ".", "!")):
        dramatic_words.add(i)
KEEP, KEEP_LONG = C.get("PAUSE_KEEP", 0.30), C.get("PAUSE_KEEP_LONG", 0.62)
cuts = []
for q0, q1 in runs:
    if q0 < START or q1 > END:
        continue
    long_ = any(words[i][1] - 0.2 <= q0 <= words[i][1] + 0.35 for i in dramatic_words if i < len(words))
    long_ |= any(q0 < o < q1 for o in OFFSETS[1:])     # breath where two recordings join
    keep = KEEP_LONG if long_ else KEEP
    c0, c1 = q0 + keep * 0.55, q1 - keep * 0.45
    if c1 - c0 > 0.08:
        cuts.append((c0, c1))
# filler words ("um", "uh", ...) are cut out as well
FILLERS = {"um", "umm", "uh", "uhh", "hmm", "erm", "ah", "mm"}
if C.get("CUT_FILLERS", True):
    for s0_, e0_, t_ in words:
        if t_.strip().strip(",.").lower() in FILLERS and START < s0_ and e0_ < END:
            cuts.append((s0_ - 0.02, e0_ + 0.04))
cuts.sort()
merged = []
for c in cuts:
    if merged and c[0] <= merged[-1][1]:
        merged[-1] = (merged[-1][0], max(merged[-1][1], c[1]))
    else:
        merged.append(c)
cuts = merged
snap = lambda t: round(t * FPS) / FPS
segs, t = [], START
for c0, c1 in cuts:
    segs.append((snap(t), snap(c0)))
    t = c1
segs.append((snap(t), snap(END)))
segs = [s for s in segs if s[1] - s[0] > 1 / FPS]

def to_new(t_orig):
    acc_ = 0.0
    for s0, s1 in segs:
        if t_orig < s0:
            return acc_
        if t_orig <= s1:
            return acc_ + t_orig - s0
        acc_ += s1 - s0
    return acc_

T = to_new
TW = lambda i: to_new(words[i][0])                 # new-timeline start of word i
BODY = sum(s1 - s0 for s0, s1 in segs)
OUTRO = 2.8 if C.get("END_CARD", "LEARN MORE") else 0.0
TOTAL = BODY + OUTRO
print(f"segments: {len(segs)}  body {BODY:.2f}s  total {TOTAL:.2f}s (raw {DUR:.2f}s)")

# ---------------------------------------------------------------- studio voice
VOICE_CHAIN = ",".join([
    "highpass=f=70:poles=2", "afftdn=nr=8:nf=-48:tn=1",
    "equalizer=f=130:t=q:w=0.9:g=1.5", "equalizer=f=520:t=q:w=1.1:g=-3",
    "equalizer=f=2900:t=q:w=0.9:g=6", "equalizer=f=5200:t=q:w=1.0:g=6", "highshelf=f=9000:g=2",
    "deesser=i=0.4:m=0.5:f=0.5",
    "acompressor=threshold=-21dB:ratio=3:attack=6:release=140:knee=4:makeup=2",
    "alimiter=limit=0.89:attack=3:release=60:level=disabled",
])
voice = os.path.join(TMP, "voice.wav")
run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-vn", "-af", VOICE_CHAIN, "-ac", "2", "-ar", "48000",
     "-c:a", "pcm_s24le", voice])
fade = 0.012
parts = [f"[0:a]atrim={s0}:{s1},asetpts=PTS-STARTPTS,afade=t=in:d={fade},"
         f"afade=t=out:st={s1 - s0 - fade}:d={fade}[a{i}]" for i, (s0, s1) in enumerate(segs)]
graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=0:a=1,apad=whole_dur={TOTAL}[aout]"
cut = os.path.join(TMP, "cut.wav")
run(["ffmpeg", "-v", "error", "-y", "-i", voice, "-filter_complex", graph, "-map", "[aout]", "-c:a", "pcm_s24le", cut])
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", cut, "-af", "loudnorm=I=-14:TP=-1:LRA=7:print_format=json",
                       "-f", "null", "-"], capture_output=True, text=True).stderr
m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1:LRA=7:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
audio = os.path.join(TMP, "audio.m4a")
run(["ffmpeg", "-v", "error", "-y", "-i", cut, "-af", ln, "-ar", "48000", "-c:a", "aac", "-b:a", "256k", audio])

# ---------------------------------------------------------------- typography
cap_groups = tt.build_groups(GROUPS, words, to_new, BODY)
statements = []
for i0, i1, lines, kind in STATEMENTS:
    t0, t1 = TW(i0) - 0.15, to_new(words[i1 - 1][1]) + 0.35
    if kind == "sequence":
        t1 += 1.0                                   # let the final number land
    statements.append(tt.Statement(lines, [TW(wi) for _, _, wi in lines], t0, t1, kind))
for st in statements:
    print(f"statement {st.kind:8s} {st.t0:6.2f}-{st.t1:6.2f}s  {st.lines[0][0] if st.lines else ''}")

def gray_amount(t):
    g = 0.0
    for st in statements:
        a_, b_ = st.t0 - 0.25, st.t1
        if a_ <= t < b_ + 0.5:
            g = max(g, ease((t - a_) / 0.5) * (1 - ease((t - b_) / 0.5)))
    return g

# ---------------------------------------------------------------- cutaways
class ClipShot:
    """A real B-roll clip, cover-fitted to 9:16, slow push-in, colour matched to the speaker."""

    def __init__(self, path, dur, start=0.0, exposure=0.42, zoom=0.06):
        self.dur, self.zoom = dur, zoom
        info = probe(path, "stream=color_transfer")
        self.hdr = info.get("color_transfer") == "arib-std-b67"
        mat = "bt2020" if self.hdr else "bt709"
        vf = (f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
              f"scale=in_color_matrix={mat}:in_range=tv:out_range=pc,format=rgb48le")
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(start), "-i", path, "-t", str(dur + 1),
                                   "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], stdout=subprocess.PIPE)
        self.exposure, self.i, self.last = exposure, -1, None

    def __call__(self, t):
        want = int(t * FPS)
        while self.i < want:
            buf = self.p.stdout.read(W * H * 6)
            if len(buf) < W * H * 6:
                break
            self.last = np.frombuffer(buf, "<u2").reshape(H, W, 3).astype(np.float32) / 65535
            self.i += 1
        fr = self.last if self.last is not None else np.zeros((H, W, 3), np.float32)
        if not self.hdr:
            fr = srgb_to_hlg(fr, white=self.exposure)
        z = 1 + self.zoom * min(t / max(self.dur, 0.1), 1)
        cw, ch = W / z, H / z
        return resize_f(fr, (W, H), box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))


def make_card(path, width):
    im = Image.open(path).convert("RGB")
    target = (width, round(im.height * width / im.width))
    if width > im.width * 1.3:
        mid = (round((im.width + width) / 2), round((im.height + target[1]) / 2))
        im = im.resize(mid, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=1))
    im = im.resize(target, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))
    r, pad = 16, 40
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    card = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", card.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + im.width, pad + im.height + 10), r, fill=150)
    card.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
    inner = im.convert("RGBA"); inner.putalpha(mask)
    card.alpha_composite(inner, (pad, pad))
    return layer_to_hlg(np.asarray(card).astype(np.float32) / 255, white=0.45)


DIM = srgb_to_hlg(np.array([8, 10, 14], np.float32) / 255)

def soft_blur(fr):
    small = resize_f(fr, (W // 12, H // 12), resample=Image.BILINEAR)
    return resize_f(small, (W, H), resample=Image.BICUBIC)


class Photos:
    """Photo / screenshot cards over the blurred, dimmed speaker, slow swipe between them."""

    def __init__(self, images, dur):
        self.dur = dur
        self.cards = []
        for p_ in images:
            im = Image.open(p_)
            w_ = 1000 if im.width >= im.height else 680
            self.cards.append(make_card(p_, w_))

    def __call__(self, fr, t):
        d, n = self.dur, len(self.cards)
        u = t / d
        fade_in, fade_out = ease(t / 0.45), ease((d - t) / 0.40)
        bg = soft_blur(fr) * 0.55 + DIM * 0.45
        mm = fade_in * fade_out
        base = fr * (1 - mm) + bg * mm
        seg = d / n
        for i, card in enumerate(self.cards):
            a_in = 1.0 if i == 0 else ease((t - i * seg + 0.35) / 0.7)
            a_out = 1.0 if i == n - 1 else 1 - ease((t - (i + 1) * seg + 0.35) / 0.7)
            alpha = (fade_in if i == 0 else a_in) * (fade_out if i == n - 1 else a_out)
            if alpha <= 0.003:
                continue
            dx = -60 * u + (520 * (1 - a_in) if i else 0) - (520 * (1 - a_out) if i < n - 1 else 0)
            sc = 1.0 + 0.035 * u
            c = resize_f(card, (round(card.shape[1] * sc), round(card.shape[0] * sc)))
            over(base, c, (W - c.shape[1]) / 2 + dx, 470 - c.shape[0] / 2, alpha)
        return base


SHOT_CLASSES = {n: getattr(flow, n) for n in ("Phone", "Hospital", "Queue", "BusyLobby", "Payment", "Blood", "Lobby", "Bill")}
REPLACE, OVERLAY = [], []          # (t0, t1, fn)
for cw in CUTAWAYS:
    if cw["type"] == "clip":
        a_ = TW(cw["from_word"]) - 0.30
        b_ = to_new(words[cw["to_word"] - 1][1]) + 0.25
        REPLACE.append((a_, b_, ClipShot(P(cw["file"]), b_ - a_, cw.get("clip_start", 0.0), cw.get("exposure", 0.42))))
    elif cw["type"] == "flow":
        shots = cw["shots"]
        end = TW(cw["end_word"]) - 0.10
        for i, (wi, name) in enumerate(shots):
            a_ = TW(wi) - 0.30
            b_ = (TW(shots[i + 1][0]) - 0.30 + 0.45) if i + 1 < len(shots) else end
            REPLACE.append((a_, b_, SHOT_CLASSES[name](b_ - a_)))
    elif cw["type"] == "photos":
        a_ = TW(cw["from_word"]) - 0.10
        b_ = to_new(words[cw["to_word"] - 1][1]) + 0.35
        OVERLAY.append((a_, b_, Photos([P(x) for x in cw["images"]], b_ - a_)))
for a_, b_, fn in REPLACE + OVERLAY:
    print(f"cutaway {type(fn).__name__:10s} {a_:6.2f}-{b_:6.2f}s")
DISSOLVE = 0.45

# ---------------------------------------------------------------- logo + end card
logo = Image.open(LOGO)
lw = 175
logo_small = np.asarray(logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)).astype(np.float32) / 255
logo_small[..., 3] = np.clip(logo_small[..., 3] * 1.25, 0, 1)
logo_small = layer_to_hlg(logo_small, white=0.60)
LOGO_POS = (W - lw - 64, 150)

def make_cta(text):
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

# ---------------------------------------------------------------- video
crop_w = min(SRC_W, round(SRC_H * 9 / 16 / 2) * 2)
crop = f"crop={crop_w}:{SRC_H}:{(SRC_W - crop_w) // 2}:0," if SRC_W / SRC_H > 9 / 16 + 0.005 else ""
mat = "bt2020" if HDR_SRC else "bt709"
vf = (f"{crop}scale={W}:{H}:flags=lanczos,unsharp=5:5:0.3:5:5:0,"
      f"scale=in_color_matrix={mat}:in_range=tv:out_range=pc,format=rgb48le")
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", vf, "-r", str(FPS),
                        "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], stdout=subprocess.PIPE)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
                        "-vf", "scale=out_color_matrix=bt2020:in_range=pc:out_range=tv,format=yuv420p10le",
                        "-c:v", "libx265", "-preset", "medium", "-crf", "16", "-tag:v", "hvc1",
                        "-x265-params", "log-level=error:colorprim=bt2020:transfer=arib-std-b67:"
                                        "colormatrix=bt2020nc:range=limited",
                        "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                        "-colorspace", "bt2020nc", "-color_range", "tv",
                        "-c:a", "copy", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)

FOCUS_Y = 0.30
FRAMES = [(1.00, 1.05), (1.20, 1.15), (1.08, 1.13), (1.26, 1.20), (1.04, 1.00), (1.14, 1.20)]
PUSH = C.get("PUSH_IN")
PUSH_FROM, PUSH_TO = (TW(PUSH[0]), to_new(words[PUSH[1] - 1][1]) + 0.3) if PUSH else (1e9, 1e9)

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
            if not HDR_SRC:
                fr = srgb_to_hlg(fr, white=0.42)
            if PUSH_FROM <= t < PUSH_TO:
                z = 1.04 + 0.14 * ease((t - PUSH_FROM) / (PUSH_TO - PUSH_FROM))
            else:
                z0, z1 = FRAMES[k % len(FRAMES)]
                z = z0 + (z1 - z0) * ease((src_i - f0) / max(f1 - f0, 1))
            fr = zoom(fr, z)
            act = []
            for a_, b_, fn in REPLACE:
                if a_ <= t < b_:
                    act.append((ease((t - a_) / DISSOLVE) * ease((b_ - t) / DISSOLVE), fn(t - a_)))
            if act:
                tot = sum(wg for wg, _ in act)
                fr = fr * (1 - min(tot, 1.0)) + sum(wg * f_ for wg, f_ in act) / tot * min(tot, 1.0)
            hide = 0.0
            for a_, b_, fn in OVERLAY:
                if a_ <= t < b_:
                    fr = fn(fr, t - a_)
                    hide = max(hide, ease((t - a_) / 0.4) * ease((b_ - t) / 0.4))
            g = gray_amount(t)
            if g > 0:
                Y = (fr @ np.array([0.2627, 0.6780, 0.0593], np.float32))[..., None]
                fr = (fr * (1 - 0.90 * g) + Y * 0.90 * g) * (1 - 0.50 * g)
            for st in statements:
                lay = st.render(t)
                if lay:
                    over(fr, *lay)
            for grp in (cap_groups if g < 0.25 else ()):
                lay = grp.render(t)
                if lay:
                    over(fr, *lay)
            over(fr, logo_small, *LOGO_POS, ease(t / 0.6) * (1 - hide))
            write(fr)
            last = fr
            out_t += 1 / FPS
        src_i += 1

if OUTRO:
    cta = make_cta(C.get("END_CARD", "LEARN MORE"))
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
print("wrote", OUT)

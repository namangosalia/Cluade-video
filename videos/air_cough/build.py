#!/usr/bin/env python3
"""Air pollution x heart: man coughing (real footage) -> smoggy skyline, script captions.

    python3 videos/air_cough/build.py

0-2 s: the coughing clip at normal speed with its own sound; captions start on the cough.
2-5 s of the clip: smooth slow motion (half speed, in-between frames from the real motion).
Then a slow dissolve into the smoggy skyline (raw GIF frames blended, slow push-in) for the
rest of the script. Captions: centred bold white sans in Title Case with a soft shadow (as the
reference), key words coloured (amber = pollution, red = heart). Ends on "Learn More." No logo.
"""
import math, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True)
OUT = os.path.join(HERE, "output", "air_pollution_cough_9x16.mp4"); os.makedirs(os.path.dirname(OUT), exist_ok=True)
# elegant caption type: white Inter Medium, highlights in soft blues (SemiBold); swap the files to change font
FONT_BODY = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
FONT_HL = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
SIZE = 60
AMBER = (150, 200, 255)     # {...} highlight: soft sky blue
RED = (96, 160, 255)        # [...] highlight: deeper blue (heart words)
CRIMSON = (236, 84, 84)     # <...> highlight: red
WHITE = (255, 255, 255)
_fc = {}
def fnt(path, size):
    if (path, size) not in _fc:
        _fc[(path, size)] = ImageFont.truetype(path, size)
    return _fc[(path, size)]

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ------------------------------------------------------------------ script: (start, end, text); {word} amber, [word] red
# {..} soft blue, [..] deep blue, <..> red; 4th field: slow zoom-in on that line
CAPS = [
    (0.85, 3.85, "Everyone Talks About {Air Pollution.}", False),
    (3.95, 6.75, "And What It Does To Our {Lungs.}", False),
    (6.85, 9.65, "But What Can We Do About It?", False),
    (9.75, 13.75, "<The Fact:> Air Pollution Also Harms Our [Hearts.]", False),
    (30.65, 33.15, "[Today!]", True),
]
# paired statements: the first moves up when the second appears beneath it; both stay in one frame
# (t_first, t_second, t_end, first, second, zoom_second)
PAIRS = [
    (13.85, 18.05, 22.05, "It Can Increase The Risk Of <Heart Attacks> And <Strokes>",
     "Especially With <Diabetes> Or <High Blood Pressure.>", False),
    (22.15, 25.35, 30.55, "We <Can't> Fix The Air {Overnight.}",
     "But We {Can} Find Out Where [Our Heart Health Stands]", True),            # main CTA line, 1 s longer
]
CTA_START = 33.25         # original ending: soft grey + white "LEARN MORE" pill card
TOTAL = 37.6
CLIP_END = 8.0            # 2 s at 1x + 3 s at 0.5x
SKY_IN = 7.2              # dissolve into the skyline starts

def tokens(text):
    out, mode = [], None
    for raw in text.split(" "):
        w = raw
        if w.startswith("{"): mode, w = AMBER, w[1:]
        elif w.startswith("["): mode, w = RED, w[1:]
        elif w.startswith("<"): mode, w = CRIMSON, w[1:]
        end = any(c in w for c in "}]>")
        w = w.replace("}", "").replace("]", "").replace(">", "")
        out.append((w, mode or WHITE))
        if end: mode = None
    return out

def block_h(text, size_scale=1.0):
    sz = int(SIZE * size_scale); f = fnt(FONT_BODY, sz); fh = fnt(FONT_HL, sz)
    fo = lambda col: f if col == WHITE else fh
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); toks = tokens(text); sp = d.textlength(" ", font=f)
    tw_ = sum(d.textlength(x, font=fo(c)) for x, c in toks) + sp * (len(toks) - 1)
    asc, desc = f.getmetrics()
    return (asc + desc) * 1.12 * (1 if tw_ <= 860 else 2)

def caption_layer(text, a, size_scale=1.0, cy=1400):
    sz = int(SIZE * size_scale)
    f = fnt(FONT_BODY, sz); fh = fnt(FONT_HL, sz)
    fo = lambda col: f if col == WHITE else fh
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    toks = tokens(text); sp = d.textlength(" ", font=f)
    tw_ = lambda l: sum(d.textlength(x, font=fo(c)) for x, c in l) + sp * (len(l) - 1)
    if tw_(toks) <= 860:
        lines = [toks]
    else:                                                   # two balanced lines (no orphan words)
        best = min(range(1, len(toks)), key=lambda i: max(tw_(toks[:i]), tw_(toks[i:])))
        lines = [toks[:best], toks[best:]]
    asc, desc = f.getmetrics(); lh = (asc + desc) * 1.12
    y = cy - lh * len(lines) / 2
    for line in lines:
        x = (W - tw_(line)) / 2
        for word, col in line:
            d.text((x, y), word, font=fo(col), fill=col + (int(255 * a),))
            x += d.textlength(word, font=fo(col)) + sp
        y += lh
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(12)).point(lambda v: min(255, int(v * 1.25))))
    sh.alpha_composite(img)
    return np.asarray(sh).astype(np.float32) / 255

# ------------------------------------------------------------------ footage: 1x then smooth half-speed slow motion
src = os.path.join(HERE, "raw", "cough.mp4")
clip = os.path.join(TMP, "clip_9x16.mp4")
# original full frame (no zoom), fitted to the width on plain black (cinematic letterbox), captions below it
crop = "scale=1080:-2:flags=lanczos,unsharp=5:5:0.4:5:5:0,pad=1080:1920:0:(oh-ih)/2-120:black"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex",
                f"[0:v]trim=0:2,setpts=PTS-STARTPTS,fps={FPS}[a];"
                f"[0:v]trim=2:5,setpts=2*(PTS-STARTPTS),minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1[b];"
                f"[a][b]concat=n=2:v=1:a=0,{crop}[v]", "-map", "[v]", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", clip],
               check=True)
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", clip, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
last_clip = None
def clip_frame():
    global last_clip
    b = dec.stdout.read(W * H * 3)
    if len(b) == W * H * 3:
        last_clip = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.float32)
    return last_clip

# ------------------------------------------------------------------ smoggy skyline: GIF frames de-banded, slow blend, push-in
gif = Image.open(os.path.join(HERE, "img", "skyline.gif"))
sky = []
for fr in ImageSequence.Iterator(gif):
    p = os.path.join(TMP, "sky_in.png"); q = os.path.join(TMP, f"sky_{len(sky)}.png")
    fr.convert("RGB").save(p)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-vf",
                    "gradfun=strength=1.8:radius=28,scale=2160:-1:flags=lanczos,gradfun=strength=1.4:radius=32", q], check=True)
    sky.append(np.asarray(Image.open(q).convert("RGB")).astype(np.float32))
SH, SW = sky[0].shape[:2]
def sky_frame(t):
    u = (t - SKY_IN) / (TOTAL - SKY_IN)
    k = (t - SKY_IN) / 4.5                                   # one GIF frame every 4.5 s, blended slowly
    i0 = int(k) % len(sky); i1 = (i0 + 1) % len(sky); f = ease(k - int(k))
    img = sky[i0] * (1 - f) + sky[i1] * f
    z = 1.0 + 0.16 * u
    ch = SH / z; cw = ch * 9 / 16
    cx = SW * 0.47 + SW * 0.05 * u                           # around the sun, drifting slightly
    x0 = min(max(cx - cw / 2, 0), SW - cw); y0 = (SH - ch) * 0.5
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    return np.asarray(im).astype(np.float32)

# ------------------------------------------------------------------ sound: original cough + street, then low city ambience
aud_src = os.path.join(TMP, "orig.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex",
                "[0:a]atrim=0:2,asetpts=PTS-STARTPTS[a];[0:a]atrim=2:5,asetpts=PTS-STARTPTS,atempo=0.5[b];"
                "[a][b]concat=n=2:v=0:a=1,aresample=48000,pan=stereo|c0=c0|c1=c0", "-ac", "2", aud_src], check=True)
w_ = wave.open(aud_src); orig = np.frombuffer(w_.readframes(w_.getnframes()), np.int16).astype(np.float32).reshape(-1, 2)[:, 0] / 32768
sr = 48000; n = int(TOTAL * sr); tt = np.arange(n) / sr
noise = np.random.default_rng(5).standard_normal(n).astype(np.float32)
rum = np.cumsum(noise); rum -= np.convolve(rum, np.ones(4800) / 4800, "same"); rum /= np.abs(rum).max() + 1e-9
mix = rum * 0.10 * np.clip((tt - 1.6) / 1.0, 0, 1)            # soft ambience under everything after the cough
o = np.zeros(n, np.float32); o[:min(n, len(orig))] = orig[:n] * 1.6
o *= np.clip((2.1 - tt) / 0.3, 0, 1)                        # keep only the cough (0-2 s); no honking street noise after
mix += o
for (s0, s1, text, _) in CAPS + [(p_[1], p_[2], p_[4], 0) for p_ in PAIRS] + [(p_[0], p_[1], p_[3], 0) for p_ in PAIRS]:
    if "Heart" in text or "Today" in text:
        b = s0 + 0.2
        while b < s1 - 0.2:
            for off, amp in ((0.0, 1.0), (0.22, 0.6)):
                q0, L = int((b + off) * sr), int(0.16 * sr)
                if q0 + L < n:
                    kk = np.arange(L) / sr
                    mix[q0:q0 + L] += 0.35 * amp * np.sin(2 * np.pi * 52 * kk) * np.exp(-kk * 28)
            b += 0.95
mix *= np.minimum(1, (TOTAL - tt) / 1.5)
aud = os.path.join(TMP, "sound.wav")
with wave.open(aud, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes((np.clip(np.stack([mix, mix], 1), -1, 1) * 32767 * 0.9).astype("<i2").tobytes())

# ------------------------------------------------------------------ Learn More card (same as the earlier reels)
def make_cta(text="LEARN MORE"):
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 38)
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
    return img
CTA = make_cta()
GREY_BG = None

# ------------------------------------------------------------------ render
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                        "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                        "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "192k",
                        "-af", "loudnorm=I=-16:TP=-1.5", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.30 * (((xx - W / 2) / (W / 1.3)) ** 2 + ((yy - H / 2) / (H / 1.3)) ** 2))[..., None].clip(0.6, 1)
MID_FROM = 9.7             # captions after the coughing clip sit mid-screen (clear of Instagram's bottom UI)
def cap_y(s0):
    return 960 if s0 >= MID_FROM else 1400
BAND_LO = (1 - 0.35 * np.exp(-((yy[:, :1] - 1400) / 260) ** 2))[..., None]   # gentle darkening behind captions
BAND_MID = (1 - 0.35 * np.exp(-((yy[:, :1] - 960) / 260) ** 2))[..., None]
for fi in range(round(TOTAL * FPS)):
    t = fi / FPS
    fr = clip_frame() if t < CLIP_END + 0.5 else last_clip
    if t >= SKY_IN:
        m = ease((t - SKY_IN) / 1.4)
        fr = fr * (1 - m) + sky_frame(t) * m
    wb = ease((t - (MID_FROM - 0.5)) / 0.5)
    fr = fr * VIG * (BAND_LO * (1 - wb) + BAND_MID * wb)
    if t >= CTA_START:                                          # original Learn More ending
        mm = ease((t - CTA_START) / 0.8)
        if GREY_BG is None:
            g_ = Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).resize((18, 32), Image.BILINEAR).resize((W, H), Image.BICUBIC)
            lum = (np.asarray(g_).astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
            GREY_BG = np.array([92, 92, 94], np.float32) * 0.85 + lum * 0.15
        fr = fr * (1 - mm) + GREY_BG * mm
        a = ease((t - CTA_START - 0.7) / 0.6)
        if a > 0:
            sc_ = 0.97 + 0.03 * a
            c = CTA.resize((round(CTA.width * sc_), round(CTA.height * sc_)), Image.LANCZOS)
            ca = np.asarray(c).astype(np.float32) / 255
            x0, y0 = (W - c.width) // 2, (H - c.height) // 2
            al = ca[..., 3:4] * a
            fr[y0:y0 + c.height, x0:x0 + c.width] = fr[y0:y0 + c.height, x0:x0 + c.width] * (1 - al) + ca[..., :3] * 255 * al
    for (ta, tb, te, txa, txb, zb) in PAIRS:
        if ta - 0.05 <= t < te:
            out_a = 1 - ease((t - (te - 0.3)) / 0.3)
            scb = (1 + 0.08 * ease((t - tb) / (te - tb))) if zb else 1.0
            ha, hb, gap = block_h(txa), block_h(txb, scb), 36
            k = ease((t - tb) / 0.6)                                # first line glides up as the second arrives
            cy0 = cap_y(ta)
            ya = cy0 + k * ((-(ha + gap + hb) / 2 + ha / 2))
            La = caption_layer(txa, ease((t - ta) / 0.35) * out_a, 1.0, ya)
            fr = fr * (1 - La[..., 3:4]) + La[..., :3] * 255 * La[..., 3:4]
            if t >= tb - 0.05:
                yb = cy0 + (ha + gap + hb) / 2 - hb / 2
                Lb = caption_layer(txb, ease((t - tb - 0.15) / 0.45) * out_a, scb, yb)
                fr = fr * (1 - Lb[..., 3:4]) + Lb[..., :3] * 255 * Lb[..., 3:4]
    for s0, s1, text, zoom in CAPS:
        if s0 - 0.05 <= t < s1:
            a = ease((t - s0) / 0.35) * (1 - ease((t - (s1 - 0.3)) / 0.3))
            base = 1.25 if text == "[Today!]" else 1.0
            sc = base * (1 + 0.08 * ease((t - s0) / (s1 - s0))) if zoom else base    # slow, slight zoom-in
            L = caption_layer(text, a, sc, cap_y(s0))
            fr = fr * (1 - L[..., 3:4]) + L[..., :3] * 255 * L[..., 3:4]
    g = np.random.default_rng(fi).standard_normal((H // 2, W // 2)).astype(np.float32) * 3.0
    fr = fr + np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", OUT)

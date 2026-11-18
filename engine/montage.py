#!/usr/bin/env python3
"""Cinematic slow-motion montage from short keyframe GIFs (or image sequences).

    python3 engine/montage.py videos/<slug>/montage_config.py

Each scene is a list of keyframes. They become a smooth clip either by motion
interpolation (small changes: real in-between motion) or by slow holds with soft
cross-dissolves (big pose changes: no warping), then: de-band + upscale, 9:16 crop framed
on the subject, continuous slow push-in, light smog, fine grain, gentle vignette.
Statements fade and rise slowly in the lower third; scenes cross-dissolve; Learn More + logo.
Output: 1080x1920 30 fps H.264 SDR, original ambient sound with a heartbeat under heart lines.
"""
import glob, math, os, runpy, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ENGINE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(ENGINE)
CFG = os.path.abspath(sys.argv[1]); VDIR = os.path.dirname(CFG); C = runpy.run_path(CFG)
P = lambda p: p if os.path.isabs(p) else os.path.join(VDIR, p)
W, H, FPS = 1080, 1920, 30
ANTON = os.path.join(REPO, "assets", "fonts", "Anton-Regular.woff"); INTER = "/usr/share/fonts/opentype/inter/"
CREAM, WHITE, RED = (240, 214, 158), (255, 255, 255), (226, 60, 50)
TMP = os.path.join(VDIR, ".tmp_montage"); os.makedirs(TMP, exist_ok=True)

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

_f = {}
def font(kind, size):
    if (kind, size) not in _f:
        _f[(kind, size)] = ImageFont.truetype(ANTON if kind == "anton" else INTER + f"Inter-{kind}.otf", size)
    return _f[(kind, size)]

# ------------------------------------------------------------------ scene clips (keyframes -> smooth 30 fps)
def build_clip(k, sc):
    if sc.get("video"):
        # real footage (e.g. a Google Flow / Veo MP4): slow it down, synthesise the in-between frames
        # from genuine motion (smooth slow motion), square-crop for the 9:16 framing step
        out = os.path.join(TMP, f"scene{k}.mp4")
        slow = sc.get("slow", 1.6)
        vf = (f"setpts={slow}*PTS,minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
              "scale=1016:1016:force_original_aspect_ratio=increase:flags=lanczos,crop=1016:1016,"
              f"tpad=stop_mode=clone:stop_duration={sc['dur']}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(sc.get("start", 0)), "-i", P(sc["video"]), "-an",
                        "-vf", vf, "-t", str(sc["dur"]), "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv444p", out],
                       check=True)
        return out
    frames = sorted(glob.glob(P(sc["frames"])))
    n = len(frames); dur = sc["dur"]
    hold = dur / n                                            # seconds per keyframe
    out = os.path.join(TMP, f"scene{k}.mp4")
    # de-band each keyframe (GIF palette) and bring to a common square size
    pre = os.path.join(TMP, f"s{k}_%02d.png")
    for i, f in enumerate(frames):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-vf",
                        "format=rgb24,gradfun=strength=1.6:radius=24,scale=1016:1016:flags=lanczos,gradfun=strength=1.1:radius=32",
                        pre % (i + 1)], check=True)
    if sc.get("method") == "interp":
        vf = f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
    else:                                                     # hold, then a soft blend into the next keyframe
        vf = f"framerate=fps={FPS}:interp_start=85:interp_end=170"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", f"1/{hold}", "-i", pre.replace("%02d", "%02d"),
                    "-vf", vf + f",tpad=stop_mode=clone:stop_duration={hold}", "-t", str(dur),
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv444p", out], check=True)
    return out

class Clip:
    def __init__(self, path):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE)
        self.last, self.i = None, -1
    def frame(self, t):
        want = int(t * FPS)
        while self.i < want:
            b = self.p.stdout.read(1016 * 1016 * 3)
            if len(b) < 1016 * 1016 * 3:
                break
            self.last = np.frombuffer(b, np.uint8).reshape(1016, 1016, 3); self.i += 1
        return self.last

def framed(img, sc, u):
    """9:16 window on the subject, slow continuous push-in."""
    S_ = img.shape[0]
    z = 1.0 + sc.get("push", 0.10) * u
    ch = S_ / z; cw = ch * 9 / 16
    cx = sc.get("x", 0.5) * S_
    x0 = min(max(cx - cw / 2, 0), S_ - cw); y0 = (S_ - ch) * sc.get("y", 0.4)
    im = Image.fromarray(img).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=45, threshold=2))
    return np.asarray(im).astype(np.float32)

# light drifting smog + particles (shared look with the other awareness reels)
def noise_field(seed, scale):
    r = np.random.default_rng(seed)
    small = r.random((H // scale + 4, W // scale + 4)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(((W // scale + 4) * scale, (H // scale + 4) * scale), Image.BICUBIC)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(scale * 0.6))).astype(np.float32) / 255
HZ1, HZ2 = noise_field(3, 120), noise_field(4, 60)
def haze(t):
    o1, o2 = int(t * 12) % 240, int(t * 22) % 120
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    return (0.16 + 0.16 * HZ1[:H, o1:o1 + W] + 0.08 * HZ2[:H, o2:o2 + W]) * (0.7 + 0.3 * (1 - y))
R = np.random.default_rng(1)
PART = [(R.uniform(0, W), R.uniform(0, H), R.uniform(1.2, 3.0), R.uniform(4, 14), R.uniform(0, 6.28)) for _ in range(110)]
def particles(t):
    lay = Image.new("L", (W, H), 0); d = ImageDraw.Draw(lay)
    for x, y, r_, sp, ph in PART:
        xx = (x + sp * t * 3) % W; yy = (y - sp * t + 8 * math.sin(t * 0.7 + ph)) % H
        d.ellipse((xx - r_, yy - r_, xx + r_, yy + r_), fill=int(80 + 60 * math.sin(t + ph) ** 2))
    return np.asarray(lay.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255

# ------------------------------------------------------------------ text
def text_layer(lines, t, dur, cy, hold=False):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    blocks = []
    for text, style in lines:
        big = style in ("big", "key", "red")
        f = font("anton", 112) if big else font("Medium", 50)
        rows, cur = [], ""
        for w_ in text.split():
            tr = (cur + " " + w_).strip()
            if d.textlength(tr, font=f) > W - 150 and cur:
                rows.append(cur); cur = w_
            else:
                cur = tr
        rows.append(cur)
        col = {"big": WHITE, "key": CREAM, "red": RED}.get(style, WHITE)
        blocks += [(r_, f, col, 0.98 if big else 1.3) for r_ in rows]
    hts = [(b[1].getmetrics()[0] + b[1].getmetrics()[1]) * b[3] for b in blocks]
    y = cy - sum(hts) / 2
    out_a = 1.0 if hold else 1 - ease((t - (dur - 0.7)) / 0.7)
    for i, ((text, f, col, _), hh) in enumerate(zip(blocks, hts)):
        t_in = 0.35 + i * min(0.55, dur * 0.35 / max(len(blocks), 1))
        a = ease((t - t_in) / 0.8) * out_a
        rise = (1 - ease((t - t_in) / 1.2)) * 26 + t * 4
        if a > 0:
            d.text(((W - d.textlength(text, font=f)) / 2, y - rise), text, font=f, fill=col + (int(255 * a),))
        y += hh
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 1.7))))
    sh.alpha_composite(img)
    return np.asarray(sh).astype(np.float32) / 255

# ------------------------------------------------------------------ build
SCENES = C["SCENES"]; END_LINES, END_DUR = C["END"]; XF = C.get("XFADE", 0.9)
starts, t = [], 0.0
for sc in SCENES:
    starts.append(t); t += sc["dur"] - XF
END_START = t; TOTAL = END_START + END_DUR
print(f"{len(SCENES)} scenes, total {TOTAL:.1f}s")
clips = [Clip(build_clip(k, sc)) for k, sc in enumerate(SCENES)]
OUT = P(C.get("OUTPUT", "output/montage_9x16.mp4")); os.makedirs(os.path.dirname(OUT), exist_ok=True)
logo = Image.open(os.path.join(REPO, "assets", "logo_on_dark.png")); lw = 420
logo_l = np.asarray(logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)).astype(np.float32) / 255

# sound: low city ambience + heartbeat under any statement that mentions the heart
sr = 48000; n = int(TOTAL * sr); tt = np.arange(n) / sr
noise = np.random.default_rng(5).standard_normal(n).astype(np.float32)
rum = np.cumsum(noise); rum -= np.convolve(rum, np.ones(4800) / 4800, "same"); rum /= np.abs(rum).max() + 1e-9
mix = rum * 0.20 * (0.7 + 0.3 * np.sin(tt * 0.3))
for k, sc in enumerate(SCENES):
    for (lines, s0, s1) in sc["text"]:
        if any("heart" in l.lower() for l, _ in lines):
            b = starts[k] + s0 + 0.3
            while b < starts[k] + s1 - 0.3:
                for off, amp in ((0.0, 1.0), (0.22, 0.6)):
                    q0, L = int((b + off) * sr), int(0.16 * sr)
                    if q0 + L < n:
                        kk = np.arange(L) / sr
                        mix[q0:q0 + L] += 0.5 * amp * np.sin(2 * np.pi * 52 * kk) * np.exp(-kk * 28)
                b += 0.95
mix *= np.minimum(1, np.minimum(tt / 1.0, (TOTAL - tt) / 1.5))
aud = os.path.join(TMP, "sound.wav")
with wave.open(aud, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes((np.clip(np.stack([mix, mix], 1), -1, 1) * 32767 * 0.8).astype("<i2").tobytes())

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                        "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
                        "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "192k",
                        "-af", "loudnorm=I=-20:TP=-2", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.28 * (((xx - W / 2) / (W / 1.3)) ** 2 + ((yy - H / 2) / (H / 1.3)) ** 2))[..., None].clip(0.62, 1)
SHADE = (np.clip((yy[:, :1] - H * 0.55) / (H * 0.35), 0, 1) * C.get("TEXT_SHADE", 0.55))[..., None]
TEXT_Y = C.get("TEXT_Y", 1470)
for fi in range(round(TOTAL * FPS)):
    t = fi / FPS
    acc, wsum = None, 0.0
    for k, sc in enumerate(SCENES):
        ts = t - starts[k]
        if -0.01 <= ts < sc["dur"]:
            wgt = (ease(ts / XF) if k else 1.0) * (1 - ease((ts - (sc["dur"] - XF)) / XF))
            if wgt > 0:
                img = clips[k].frame(max(ts, 0))
                if img is not None:
                    f_ = framed(img, sc, ts / sc["dur"])
                    acc = f_ * wgt if acc is None else acc + f_ * wgt; wsum += wgt
    fr = acc / max(wsum, 1e-6) if acc is not None else np.full((H, W, 3), 12, np.float32)
    if t >= END_START - XF:
        e = ease((t - END_START + XF) / XF); fr = fr * (1 - e) + 12 * e
    hz = haze(t)[..., None] * C.get("HAZE", 0.6)
    fr = fr * (1 - hz) + np.array([196, 188, 172], np.float32) * hz
    fr = fr + particles(t)[..., None] * 60 * C.get("PARTICLES", 0.7)
    fr = fr * VIG
    if t < END_START:
        fr = fr * (1 - SHADE)
    for k, sc in enumerate(SCENES):
        for (lines, s0, s1) in sc["text"]:
            ts = t - starts[k] - s0
            if 0 <= ts < s1 - s0:
                L = text_layer(lines, ts, s1 - s0, TEXT_Y)
                a = L[..., 3:4]; fr = fr * (1 - a) + L[..., :3] * 255 * a
    if t >= END_START:
        te = t - END_START
        L = text_layer(END_LINES, te, END_DUR, 1000, hold=True); a = L[..., 3:4]; fr = fr * (1 - a) + L[..., :3] * 255 * a
        al = ease((te - 0.8) / 0.8)
        if al > 0:
            lh, lw_ = logo_l.shape[:2]; x0, y0 = (W - lw_) // 2, 1160
            a2 = logo_l[..., 3:4] * al; roi = fr[y0:y0 + lh, x0:x0 + lw_]; roi[:] = roi * (1 - a2) + logo_l[..., :3] * 255 * a2
    g = np.random.default_rng(fi).standard_normal((H // 2, W // 2)).astype(np.float32) * C.get("GRAIN", 3.5)
    fr = fr + np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", OUT)

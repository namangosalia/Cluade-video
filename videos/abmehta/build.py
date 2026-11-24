"""Padma Bhushan Dr A B Mehta at the Jaslok x AnginaX press conference -> vertical short in the style of Naman's
reference (the YouTube screen recording: wide shot on top, the speaker zoomed in below, kinetic callouts on the
left, small sentence captions low on screen).

- top: the original wide shot (all three on the panel); bottom: Dr Mehta (centre seat) zoomed in;
  on a few phrases the whole frame goes to him
- credentials as a readable card on the right side (PADMA BHUSHAN / Dr A B Mehta / Pioneer of Interventional
  Cardiology), 'PRESS CONFERENCE · MUMBAI' label top left; no running Hindi subtitles
- his Hindi as captions in English letters (not translated); long pauses shortened; room noise reduced
- ends on LEARN MORE
"""
import os, subprocess, wave
import cv2
import numpy as np
import noisereduce as nr
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
SRC = os.path.join(HERE, "raw", "press.mp4")
OUT = os.path.join(HERE, "output", "ab_mehta_anginax_9x16.mp4")
W, H, FPS = 1080, 1920, 25
POP = os.path.join(REPO, "assets", "fonts", "poppins-latin-800-normal.woff")
INTER = "/usr/share/fonts/opentype/inter/"
CYAN, WHITE = (52, 196, 240), (255, 255, 255)
def F(n, s): return ImageFont.truetype(INTER + n, s)
def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- audio: clean, then shorten long pauses
raw48 = os.path.join(TMP, "a48.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "48000", raw48], check=True)
w = wave.open(raw48); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
DUR = len(x) / 48000
fr_ = x[: len(x) // 480 * 480].reshape(-1, 480); db = 20 * np.log10(np.sqrt((fr_ ** 2).mean(1)) + 1e-9)
quiet = db < np.percentile(db, 15) + 3
y = nr.reduce_noise(y=x, sr=48000, y_noise=fr_[quiet].reshape(-1), stationary=True, prop_decrease=0.85, n_fft=2048)
y = nr.reduce_noise(y=y, sr=48000, stationary=False, prop_decrease=0.5, n_fft=2048)
clean = os.path.join(TMP, "clean.wav")
with wave.open(clean, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000); wf.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
SIL = float(np.percentile(db[db > -90], 90)) - 22
cuts, s_ = [], None
for i, q in enumerate(np.append(db < SIL, False)):
    if q and s_ is None: s_ = i
    if not q and s_ is not None:
        q0, q1 = s_ / 100, i / 100
        if q1 - q0 >= 0.40 and q0 > 0.1: cuts.append((q0 + 0.14, q1 - 0.14))     # keep ~0.28 s of breath
        s_ = None
START, END_T = 0.38, 45.0
keep, t0 = [], START
for s, e in cuts:
    if s > t0 + 0.04 and s < END_T: keep.append((t0, s))
    t0 = max(t0, e)
keep.append((t0, END_T))
BODY = sum(e - s for s, e in keep)
def out_of(t):
    acc = 0.0
    for s, e in keep:
        if t < s: return acc
        if t <= e: return acc + t - s
        acc += e - s
    return acc
def src_of(tn):
    acc = 0.0
    for s, e in keep:
        if tn <= acc + (e - s): return s + tn - acc
        acc += e - s
    return keep[-1][1]
END_XF, CTA_HOLD = 0.4, 2.0
TOTAL = BODY + END_XF + CTA_HOLD
print(f"{len(keep)} pieces, body {BODY:.1f}s (raw {DUR:.1f}s)")

# ---------------------------------------------------------------- framing (static camera: Dr Mehta's face ~ (492, 160), ~91 px)
cap = cv2.VideoCapture(SRC); SW, SH = int(cap.get(3)), int(cap.get(4))
FXc, FYc, FSc = 492.0, 160.0, 91.0
TOP_H = int(round(W * SH / SW))                     # 1080 x 530: the whole wide shot
def view(src, tw, th, ch, yfrac):
    asp = tw / th; cw = ch * asp
    if cw > SW: cw = SW; ch = cw / asp
    x0 = float(np.clip(FXc - cw * 0.34, 0, SW - cw)); y0 = float(np.clip(FYc - ch * yfrac, 0, SH - ch))   # him a little left: room on the right
    sc = tw / cw
    M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
    o = cv2.warpAffine(src, M, (tw, th), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    return o * 1.32 - cv2.GaussianBlur(o, (0, 0), 2.2) * 0.32
def render(src, mode, z):
    if mode == "split":
        fr = np.zeros((H, W, 3), np.float32)
        fr[:TOP_H] = cv2.resize(src, (W, TOP_H), interpolation=cv2.INTER_AREA).astype(np.float32)
        fr[TOP_H:] = view(src, W, H - TOP_H, 330 / z, 0.20)       # face high in the panel, text below it
        g = np.linspace(0, 1, 40)[:, None, None]
        fr[TOP_H - 20:TOP_H + 20] = fr[TOP_H - 20:TOP_H + 20] * (0.55 + 0.45 * np.abs(g * 2 - 1))
        return fr
    return view(src, W, H, SH / z, 0.20)
# phrases where the whole frame goes to him (source seconds); otherwise split
FULL = [(12.8, 19.0), (27.0, 34.0), (41.0, 45.0)]
def mode_at(src_t):
    return "full" if any(a <= src_t < b for a, b in FULL) else "split"

# ---------------------------------------------------------------- captions: his Hindi in English letters
CAPS = [(0.40, 6.30, "AnginaX koi medical institute ya koi doctor nahi hai,"),
        (6.90, 12.60, "balki doctor ko madad karne ke liye ek aisi sanstha hai jo modern science ka upyog karke"),
        (12.80, 18.90, "doctor ko unke patient ke analysis ke baare mein bahut hi madad karti hai."),
        (19.20, 23.30, "Ab dekhiye, human mind ki to limitations hoti hain,"),
        (23.40, 28.10, "woh maryadit hoti hai, aur ismein bhool-chook hone ki sambhavna badi hoti hai."),
        (28.40, 34.00, "To yeh bahut kam ho jaati hai. Possibilities jo anek prakar ki hoti hain,"),
        (34.00, 41.00, "woh include ho jaati hain, taaki hamara diagnosis accurate ho sake,"),
        (41.00, 45.00, "aur hum patient ko accurate salaah-suchna de sakein.")]
F_CAP = F("Inter-Medium.otf", 42)
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_CAP) > 860: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    img = Image.new("RGBA", (W, 56 * len(lines) + 40), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines): ds.text((W / 2, 20 + i * 56 + 3), ln, font=F_CAP, fill=230, anchor="ma")
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(6)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines): d.text((W / 2, 20 + i * 56), ln, font=F_CAP, fill=WHITE + (255,), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
caps = [(out_of(s), out_of(e) + 0.2, cap_layer(t)) for s, e, t in CAPS]
CAP_Y = 1500

# ---------------------------------------------------------------- kinetic callouts (left), timed on his words (source seconds)
F_BIG = ImageFont.truetype(POP, 84); F_MID = ImageFont.truetype(POP, 58); F_TAG = F("Inter-SemiBold.otf", 24)
F_SUB = F("Inter-Regular.otf", 26); F_NUM = ImageFont.truetype(POP, 30)
CALLOUTS = [
    (0.4, 6.3, [(0.4, "tag", "ANGINAX IS NOT", WHITE), (2.6, "mid", "A MEDICAL INSTITUTE", WHITE), (5.0, "mid", "A DOCTOR", WHITE)]),
    (6.9, 12.6, [(6.9, "tag", "IT IS HERE TO", WHITE), (7.6, "big", "HELP DOCTORS", CYAN), (10.6, "sub", "with modern science", WHITE)]),
    (12.8, 18.9, [(12.8, "tag", "WITH THEIR", WHITE), (15.5, "big", "PATIENT", WHITE), (16.0, "big", "ANALYSIS", CYAN)]),
    (19.2, 28.1, [(19.2, "tag", "THE HUMAN MIND HAS", WHITE), (21.6, "big", "LIMITATIONS", CYAN), (26.0, "sub", "and a real chance of error", WHITE)]),
    (28.4, 36.0, [(28.4, "tag", "THAT CHANCE BECOMES", WHITE), (29.0, "big", "MUCH SMALLER", CYAN), (31.6, "list", "ALL POSSIBILITIES", WHITE),
                  (34.5, "list", "INCLUDED", WHITE)]),
    (36.0, 41.0, [(36.4, "tag", "SO THAT THE", WHITE), (38.0, "big", "DIAGNOSIS", WHITE), (39.6, "big", "IS ACCURATE", CYAN)]),
    (41.0, 45.0, [(41.0, "tag", "AND THE PATIENT GETS", WHITE), (43.2, "big", "ACCURATE", CYAN), (43.8, "big", "ADVICE.", WHITE)]),
]
CX, CY0 = 64, 1150
def spaced(d, x, y, text, f, fill, track=4):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + track
    return x
def item_layer(kind, text, col, idx):
    f = {"tag": F_TAG, "big": F_BIG, "mid": F_MID, "list": F_MID, "sub": F_SUB}[kind]
    hgt = {"tag": 46, "big": 96, "mid": 72, "list": 78, "sub": 42}[kind]
    img = Image.new("RGBA", (W - CX, hgt + 20), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh); x0 = 0
    if kind == "list": ds.text((0, 28), f"{idx:02d}", font=F_NUM, fill=160); x0 = 70
    if kind == "tag": spaced(ds, 2, 4, text, f, 160)
    else: ds.text((x0 + 2, 4), text, font=f, fill=180)
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(7)))
    img = Image.alpha_composite(img, s2); d_ = ImageDraw.Draw(img)
    if kind == "list": d_.text((0, 26), f"{idx:02d}", font=F_NUM, fill=CYAN + (255,))
    if kind == "tag": spaced(d_, 0, 0, text, f, (220, 228, 238, 255))
    elif kind == "sub": d_.text((x0, 0), text, font=f, fill=(225, 232, 240, 255))
    else: d_.text((x0, 0), text, font=f, fill=col + (255,))
    return np.asarray(img).astype(np.float32) / 255, hgt
class Callout:
    def __init__(self, s0, s1, items):
        self.items = []; yy = 0; li = 0
        for st, kind, text, col in items:
            if kind == "list": li += 1
            arr, hgt = item_layer(kind, text, col, li)
            self.items.append((out_of(st), yy, arr)); yy += hgt + 6
        self.t0 = self.items[0][0] - 0.05; self.t1 = out_of(s1) + 0.6
    def draw(self, fr, tn, nxt):
        end = min(self.t1, nxt - 0.05) if nxt else self.t1
        if not (self.t0 <= tn < end + 0.3): return
        o = 1 - ease((tn - end) / 0.3)
        for t_, yy, arr in self.items:
            if tn < t_: continue
            p = ease((tn - t_) / 0.28); hh, ww = arr.shape[:2]
            yv = CY0 + yy + int(18 * (1 - p)); hv = min(hh, H - yv)
            al = arr[:hv, :, 3:4] * p * o
            fr[yv:yv + hv, CX:CX + ww] = fr[yv:yv + hv, CX:CX + ww] * (1 - al) + arr[:hv, :, :3] * 255 * al
CALLS = [Callout(*c) for c in CALLOUTS]

# ---------------------------------------------------------------- credentials, top right (animated in)
def cred_layer():
    img = Image.new("RGBA", (W, 230), (0, 0, 0, 0))
    lines = [("PADMA BHUSHAN", F_TAG, CYAN, True), ("Dr A B Mehta", F("Inter-Bold.otf", 46), WHITE, False),
             ("Pioneer of Interventional Cardiology", F("Inter-Regular.otf", 27), (226, 232, 240), False)]
    ys = [26, 62, 124]
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh); d = None
    def draw(dr, shadow):
        for (t, f, c, sp), y_ in zip(lines, ys):
            wv = (sum(dr.textlength(ch, font=f) + 5 for ch in t) - 5) if sp else dr.textlength(t, font=f)
            x_ = W - 56 - wv
            if sp: spaced(dr, x_ + (2 if shadow else 0), y_ + (3 if shadow else 0), t, f, 170 if shadow else c + (255,), 5)
            else: dr.text((x_ + (2 if shadow else 0), y_ + (3 if shadow else 0)), t, font=f, fill=170 if shadow else c + (255,))
        if not shadow: dr.line((W - 56 - 70, 178, W - 56, 178), fill=CYAN + (255,), width=3)
    draw(ds, True)
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(8)))
    img = Image.alpha_composite(img, s2); draw(ImageDraw.Draw(img), False)
    return np.asarray(img).astype(np.float32) / 255
CRED = cred_layer()

# credentials card on the right side (readable: solid dark card, larger type), clear of the reel's right-edge buttons
def cred_card():
    f1 = ImageFont.truetype(os.path.join(REPO, "assets", "fonts", "poppins-latin-700-normal.woff"), 30)
    f2 = F("Inter-Bold.otf", 44); f3 = F("Inter-SemiBold.otf", 25)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    t1, t2, t3 = "PADMA BHUSHAN", "Dr A B Mehta", "Pioneer of Interventional Cardiology"
    w1 = sum(d0.textlength(c, font=f1) + 5 for c in t1) - 5
    wv = int(max(w1, d0.textlength(t2, font=f2), d0.textlength(t3, font=f3))) + 64
    pad = 24
    img = Image.new("RGBA", (wv + 2 * pad, 190 + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + wv, pad + 190 + 8), 22, fill=150)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad, pad, pad + wv, pad + 190), 22, fill=(10, 16, 28, 222))
    d.rectangle((pad + wv - 6, pad + 18, pad + wv, pad + 172), fill=CYAN + (255,))
    xr = pad + wv - 30
    x = xr - w1
    for c in t1:
        d.text((x, pad + 22), c, font=f1, fill=(255, 205, 96, 255)); x += d.textlength(c, font=f1) + 5    # warm gold: the honour
    d.text((xr, pad + 66), t2, font=f2, fill=(255, 255, 255, 255), anchor="ra")
    d.text((xr, pad + 132), t3, font=f3, fill=(214, 224, 238, 255), anchor="ra")
    return np.asarray(img).astype(np.float32) / 255
CRED2 = cred_card()
CRED_X, CRED_Y = W - CRED2.shape[1] + 4, 640       # tucked to the right edge, clear of his face       # right side, below the top band, above the reel's right-hand buttons
def place_label():
    f = F("Inter-SemiBold.otf", 26)
    img = Image.new("RGBA", (W - 80, 70), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.ellipse((4, 22, 20, 38), fill=(232, 60, 60, 255))
    x = 34
    for c in "PRESS CONFERENCE  \u00b7  MUMBAI":
        d.text((x + 2, 17), c, font=f, fill=(0, 0, 0, 140)); x += d.textlength(c, font=f) + 4
    x = 34
    for c in "PRESS CONFERENCE  \u00b7  MUMBAI":
        d.text((x, 15), c, font=f, fill=(255, 255, 255, 255)); x += d.textlength(c, font=f) + 4
    return np.asarray(img).astype(np.float32) / 255
PLACE = place_label()
_g = np.clip(1 - np.arange(360, dtype=np.float32) / 360, 0, 1)
TOPSCRIM = (0.78 * _g ** 1.2)[:, None, None]
_gb = np.clip((np.arange(H, dtype=np.float32) - 1020) / 520, 0, 1)
SCRIM = (0.6 * _gb ** 1.3)[:, None, None]

def make_cta(text):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1))); f = F("Inter-SemiBold.otf", 40); track = 6
    widths = [d.textlength(ch, font=f) for ch in text]; t_w = sum(widths) + track * (len(text) - 1)
    pw, ph, pad = int(t_w + 150), 110, 34
    img = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + pw, pad + ph + 8), ph // 2, fill=110)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(14))); dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((pad, pad, pad + pw, pad + ph), ph // 2, fill=(255, 255, 255, 255))
    xx = pad + (pw - t_w) / 2; asc, desc = f.getmetrics(); yy = pad + (ph - (asc + desc)) / 2 + 2
    for ch, wd in zip(text, widths):
        dr.text((xx, yy), ch, font=f, fill=(34, 36, 40, 255)); xx += wd + track
    return np.asarray(img).astype(np.float32) / 255
CTA = make_cta("LEARN MORE")

# ---------------------------------------------------------------- audio edit
cutwav = os.path.join(TMP, "cut.wav")
fc_a = "".join(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={max(0, e - s - 0.02):.3f}:d=0.02[a{i}];"
               for i, (s, e) in enumerate(keep)) + "".join(f"[a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=0:a=1,apad=whole_dur={TOTAL:.3f}[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clean, "-filter_complex", fc_a, "-map", "[a]", "-ar", "48000", "-t", f"{TOTAL:.3f}", cutwav], check=True)
VOICE = ("highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,highshelf=f=9000:g=1.5,"
         "deesser=i=0.3,acompressor=threshold=0.08:ratio=2.8:attack=8:release=150:makeup=2")
import json
_m = subprocess.run(["ffmpeg", "-hide_banner", "-i", cutwav, "-af", VOICE + ",loudnorm=I=-14:TP=-1:LRA=7:print_format=json", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
_j = json.loads(_m[_m.rindex("{"):_m.rindex("}") + 1])
VOICE += (f",loudnorm=I=-14:TP=-1:LRA=7:measured_I={_j['input_i']}:measured_TP={_j['input_tp']}:measured_LRA={_j['input_lra']}:"
          f"measured_thresh={_j['input_thresh']}:offset={_j['target_offset']}:linear=true")

# ---------------------------------------------------------------- render
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", cutwav, "-map", "0:v", "-map", "1:a", "-af", VOICE, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                        "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", OUT],
                       stdin=subprocess.PIPE)
_pos, _cur = [0], [None]
def frame_at(k):
    if _pos[0] != k: cap.set(cv2.CAP_PROP_POS_FRAMES, k)
    ok, f = cap.read(); _pos[0] = k + 1
    if ok: _cur[0] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
    return _cur[0]
def put(fr, L, x, y, a):
    hh, ww = min(L.shape[0], H - y), min(L.shape[1], W - x)          # clip to the frame (slide-ins)
    L = L[:hh, :ww]; sub = fr[y:y + hh, x:x + ww]; al = L[..., 3:4] * a
    sub[:] = sub * (1 - al) + L[..., :3] * 255 * al
last, prev_k, prev_img = None, -1, None
for fi in range(int(round(TOTAL * FPS))):
    tn = fi / FPS
    if tn < BODY:
        st = src_of(tn); k = min(int(round(st * FPS)), int(cap.get(7)) - 1)
        src = frame_at(k)
        z = 1.0 + 0.08 * tn / BODY                                  # one slow, gentle push-in across the whole video
        fr = render(src, mode_at(st), z)
        if tn < 0.4: fr = fr * ease(tn / 0.4)
        last = fr.copy()
        fr[:360] *= (1 - TOPSCRIM); fr *= (1 - SCRIM)
        for i, c in enumerate(CALLS): c.draw(fr, tn, CALLS[i + 1].t0 if i + 1 < len(CALLS) else None)
        # (no running Hindi subtitles: Naman asked for none)
        pc = ease((tn - 0.6) / 0.6)                                   # credentials card slides in from the right
        if pc > 0:
            put(fr, CRED2, CRED_X + int(70 * (1 - pc)), CRED_Y, pc)
        pl = ease((tn - 0.3) / 0.5)
        if pl > 0: put(fr, PLACE, 40, 40, pl)
    else:
        u = tn - BODY
        blur = cv2.GaussianBlur(last, (0, 0), 26) * 0.55
        mb = ease(u / END_XF); fr = last * (1 - mb) + blur * mb
        ca = ease((u - 0.1) / 0.3)
        if ca > 0: put(fr, CTA, (W - CTA.shape[1]) // 2, (H - CTA.shape[0]) // 2, ca)
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", OUT)

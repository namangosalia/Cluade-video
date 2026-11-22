"""DD News Hindi clip + AnginaX keynote coverage, side by side (16:9, 1920x1080).

- both videos untouched (no crop, no grade), each in its own panel with its label
- sound: only the DD News clip (Naman speaking); the keynote clip is muted
- captions under the panels: the same words he speaks (Hindi / English, in English letters), average size,
  key words highlighted
"""
import os, subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output", "dd_news_keynote_side_by_side_16x9.mp4"); os.makedirs(os.path.dirname(OUT), exist_ok=True)
A_SRC, B_SRC = os.path.join(HERE, "raw", "dd_news.mp4"), os.path.join(HERE, "raw", "keynote.mp4")
W, H, FPS = 1920, 1080, 25
INTER = "/usr/share/fonts/opentype/inter/"
def F(n, s): return ImageFont.truetype(INTER + n, s)
def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)
BLUE, GOLD = (112, 182, 255), (206, 176, 118)
DUR = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", A_SRC],
                           capture_output=True, text=True).stdout)

# ---------------------------------------------------------------- layout
PW, PH, GAP = 936, 527, 16
AX, BX = (W - 2 * PW - GAP) // 2, (W - 2 * PW - GAP) // 2 + PW + GAP
PY = 250
CAP_Y = PY + PH + 50

def page():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    top = np.array([18, 24, 38], np.float32); bot = np.array([6, 8, 14], np.float32)
    g = (yy / H)[..., None]
    img = Image.fromarray(np.clip(top * (1 - g) + bot * g, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # labels above each panel
    small = F("Inter-SemiBold.otf", 26); big = F("Inter-SemiBold.otf", 40); sub = F("Inter-Regular.otf", 28)
    def spaced(x, y, text, f, fill, track=5):
        for ch in text:
            d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + track
    spaced(AX, 112, "DD NEWS HINDI", small, BLUE + (255,))
    d.text((AX, 150), "Naman Gosalia", font=big, fill=(255, 255, 255, 255))
    d.text((AX + d.textlength("Naman Gosalia", font=big) + 18, 162), "Founder of AnginaX  ·  April 6, 2025", font=sub, fill=(196, 206, 222, 255))
    spaced(BX, 112, "KEYNOTE", small, BLUE + (255,))
    d.text((BX, 150), "AnginaX Keynote for Cardiologists", font=big, fill=(255, 255, 255, 255))
    for x in (AX, BX):
        d.line((x, 220, x + 70, 220), fill=GOLD + (255,), width=3)
    # panel shadows
    sh = Image.new("L", (W, H), 0); ds = ImageDraw.Draw(sh)
    for x in (AX, BX): ds.rounded_rectangle((x, PY + 10, x + PW, PY + PH + 10), 18, fill=150)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(16)))
    return np.asarray(Image.alpha_composite(img, shadow).convert("RGB")).astype(np.float32)
PAGE = page()
MASK = Image.new("L", (PW, PH), 0); ImageDraw.Draw(MASK).rounded_rectangle((0, 0, PW - 1, PH - 1), 18, fill=255)
MASK = (np.asarray(MASK).astype(np.float32) / 255)[..., None]

# ---------------------------------------------------------------- captions (his words, highlighted)
CAPS = [   # (start, end, text) - [..] highlighted
    (0.00, 3.25, "Patient [doctor ki office] mein jaaye, usse pehle doctor ko"),
    (3.25, 6.50, "woh patient ki [poori information] on the screen hai."),
    (6.90, 10.80, "Aur then doctor will talk about that patient's [individual biomarkers]"),
    (10.80, DUR, "to eliminate, how they can be [prevented.]"),
]
F_B, F_H = F("Inter-Medium.otf", 46), F("Inter-Bold.otf", 46)
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text):
    toks, hl = [], False
    for raw in text.split():
        if raw.startswith("["): hl = True
        toks.append((raw.strip("[]"), hl))
        if raw.endswith("]") or raw.rstrip(".,").endswith("]"): hl = False
    sp = dd.textlength(" ", font=F_B)
    widths = [dd.textlength(t, font=F_H if h else F_B) for t, h in toks]
    x = (W - (sum(widths) + sp * (len(toks) - 1))) / 2
    img = Image.new("RGBA", (W, 110), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh); xx = x
    for (t, h), wd in zip(toks, widths):
        ds.text((xx, 33), t, font=F_H if h else F_B, fill=200); xx += wd + sp
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(6)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img); xx = x
    for (t, h), wd in zip(toks, widths):
        d.text((xx, 30), t, font=F_H if h else F_B, fill=(BLUE if h else (255, 255, 255)) + (255,)); xx += wd + sp
    return np.asarray(img).astype(np.float32) / 255
LAYERS = [(s, e, cap_layer(t)) for s, e, t in CAPS]

# ---------------------------------------------------------------- render
def reader(path, w, h):
    return subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={FPS},scale={w}:{h}:flags=lanczos", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
da, db = reader(A_SRC, PW, PH), reader(B_SRC, PW, PH)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", A_SRC, "-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-14:TP=-1:LRA=7",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
                        "-color_trc", "bt709", "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                        "-t", f"{DUR:.3f}", OUT], stdin=subprocess.PIPE)
la = lb = None
for fi in range(int(round(DUR * FPS))):
    t = fi / FPS
    ba = da.stdout.read(PW * PH * 3); bb = db.stdout.read(PW * PH * 3)
    if len(ba) == PW * PH * 3: la = np.frombuffer(ba, np.uint8).reshape(PH, PW, 3).astype(np.float32)
    if len(bb) == PW * PH * 3: lb = np.frombuffer(bb, np.uint8).reshape(PH, PW, 3).astype(np.float32)
    fr = PAGE.copy()
    for x, im in ((AX, la), (BX, lb)):
        sub = fr[PY:PY + PH, x:x + PW]; sub[:] = sub * (1 - MASK) + im * MASK
    for s, e, L in LAYERS:
        if s <= t < e:
            a = ease((t - s) / 0.15) * (1 - ease((t - (e - 0.15)) / 0.15)) if e < DUR else ease((t - s) / 0.15)
            al = L[..., 3:4] * a
            fr[CAP_Y:CAP_Y + 110] = fr[CAP_Y:CAP_Y + 110] * (1 - al) + L[..., :3] * 255 * al
    fr *= ease(t / 0.4) * (1 - ease((t - (DUR - 0.5)) / 0.5))       # soft fade in / out
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); da.terminate(); db.terminate()
print("wrote", OUT)

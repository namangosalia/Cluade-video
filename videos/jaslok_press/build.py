"""Jaslok x AnginaX press conference: organic cut with romanised-Hindi captions.

- Speech is Hindi; captions are the same Hindi words written in English letters (not a translation).
- Pauses and "aa / umm" fillers are cut out (short audio crossfades so the cuts stay natural).
- Small, clean captions at the bottom; no effects, no grade, the footage stays as it was shot.
"""
import os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "raw", "press.mp4")
OUT = os.path.join(HERE, "output", "jaslok_press_captioned_16x9.mp4")
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True)
W, H, FPS = 1920, 1080, 24

# ---------------------------------------------------------------- captions on the ORIGINAL timeline
LINES = [
    (0.70, 4.40, "AnginaX doctor ka tool hai, patient ka nahi."),
    (5.00, 7.45, "Ye doctor ko help karta hai, exactly."),
    (7.60, 10.45, "Ki exactly kya check karna hai body mein."),
    (11.15, 15.40, "Toh wo saare biomarkers hain, sirf chaar-paanch nahi hain."),
    (15.45, 18.80, "AnginaX ek scientific research karke,"),
    (19.85, 23.80, "precisely kuch biomarkers ko rakh ke uska analysis karta hai,"),
    (23.80, 28.35, "aur doctor ko bolta hai ki is patient ko sirf cardiovascular markers mat dekho,"),
    (28.35, 31.15, "unko metabolic dysfunction wale bhi dekho,"),
    (31.50, 33.60, "unka lifestyle pattern bhi dekho,"),
    (33.60, 36.40, "unki genetic predisposition bhi dekho."),
    (36.40, 40.00, "Aur saare combination of biomarkers, jo pehli baar jab test hota hai,"),
    (40.00, 44.30, "uske baad jo result aata hai, uske baad kaunse investigation karne chahiye."),
    (44.60, 48.20, "Doctor toh jaanta hai, lekin wo extra information se"),
    (48.20, 52.10, "doctor precise decision le sakta hai, us patient ki body ke liye."),
    (52.60, 54.20, "Toh ye generalised recommendation nahi hai."),
    (54.20, 57.60, "Har body ki alag alag recommendation hai."),
    (57.60, 60.40, "Aur wo kyun hoti hai? Because different readings,"),
    (60.40, 63.40, "har lab ke report ki different reading hai."),
    (63.95, 66.20, "General reference range nahi hai,"),
    (66.60, 68.55, "ki sau se upar hua toh aap risk pe ho,"),
    (68.55, 70.40, "aur sau se neeche hua toh aap risk pe nahi."),
    (70.40, 71.45, "Wo nahi hona chahiye."),
    (82.95, 85.80, "Toh agar wo saare combination together karke"),
    (85.80, 87.85, "jo personalised recommendation doctor ko milta hai,"),
    (88.25, 91.08, "usse doctor aapko pehle se assess kar paayega."),
    (91.50, 93.80, "Hum nahi chahte ki aapko symptoms ho,"),
    (93.80, 96.52, "chest pain ka, shortness of breath ka."),
    (96.90, 99.10, "Hum chahte hain ki aapko symptoms kabhi aaye hi nahi."),
    (100.18, 102.10, "Way before, early stage pe hi sochna hai."),
]

# ---------------------------------------------------------------- cuts: pauses and fillers
def find_pauses(wav, thr=-27.5, min_len=0.30):
    w = wave.open(wav); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    f = a[: len(a) // 320 * 320].reshape(-1, 320)
    q = 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-9) < thr
    out, i = [], 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]: j += 1
            if (j - i) * 0.02 >= min_len: out.append((i * 0.02, j * 0.02))
            i = j
        else:
            i += 1
    return out, len(a) / 16000

wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "16000", wav], check=True)
pauses, DUR = find_pauses(wav)
FILLERS = [(10.45, 11.15)]                 # "aa," before "toh wo saare biomarkers"
REMOVE = (71.60, 82.88)                    # lines cut on request: "Shayad aapka ..." to "... Lipoprotein(a) bahut high hai"
DISS = 0.40                                # sound blends softly over that cut; picture cuts cleanly mid-blend
KEEP_GAP = 0.14                            # breath left in each cut pause
cuts = []
for s, e in pauses + FILLERS:
    if e - s > KEEP_GAP:
        cuts.append((s + KEEP_GAP / 2, e - KEEP_GAP / 2))
cuts.append(REMOVE)
cuts.sort()
merged = []
for s, e in cuts:
    if merged and s <= merged[-1][1]: merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
    else: merged.append((s, e))
keep, t0 = [], 0.0
for s, e in merged:
    if s - t0 > 0.05: keep.append((t0, s))
    t0 = e
keep.append((t0, DUR))

def remap(t):
    """original time -> edited time"""
    acc = 0.0
    for s, e in keep:
        if t < s: return acc
        if t <= e: return acc + t - s
        acc += e - s
    return acc
_remap = remap
def remap(t):
    return _remap(t) - (DISS if t >= REMOVE[1] - 0.01 else 0.0)
NEW_DUR = remap(DUR)
print(f"cuts: {len(merged)}  {DUR:.1f}s -> {NEW_DUR:.1f}s")

# ---------------------------------------------------------------- cut the footage
cut_mp4 = os.path.join(TMP, "cut.mp4")
fc, XF = [], 0.02
for i, (s, e) in enumerate(keep):
    fc.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];"
              f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={XF},afade=t=out:st={max(0, e - s - XF):.3f}:d={XF}[a{i}];")
J = next(i for i, (s, e) in enumerate(keep) if s >= REMOVE[0])           # first piece after the removed lines
lenA = sum(e - s for s, e in keep[:J])
fc.append("".join(f"[v{i}][a{i}]" for i in range(J)) + f"concat=n={J}:v=1:a=1[va][aa];")
fc.append("".join(f"[v{i}][a{i}]" for i in range(J, len(keep))) + f"concat=n={len(keep) - J}:v=1:a=1[vb][ab];")
# picture: a clean camera-style cut in the middle of the sound blend (a dissolve ghosts the two framings)
fc.append(f"[va]fps={FPS},trim=0:{lenA - DISS / 2:.3f},setpts=PTS-STARTPTS[va2];[vb]fps={FPS},trim={DISS / 2:.3f},setpts=PTS-STARTPTS[vb2];"
          f"[va2][vb2]concat=n=2:v=1:a=0[v];"
          f"[aa][ab]acrossfade=d={DISS}:c1=tri:c2=tri[a]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-filter_complex", "".join(fc), "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-r", str(FPS), "-c:a", "pcm_s16le", cut_mp4], check=True)

# ---------------------------------------------------------------- clean the voice: remove the room / crowd noise
import noisereduce as nr
raw48 = os.path.join(TMP, "cut48.wav"); clean = os.path.join(TMP, "clean.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cut_mp4, "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", raw48], check=True)
w = wave.open(raw48); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
src48 = os.path.join(TMP, "src48.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", src48], check=True)
w = wave.open(src48); xs = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
noise = np.concatenate([xs[int(a * 48000):int(b * 48000)] for a, b in pauses])      # the room tone between his sentences
y = nr.reduce_noise(y=x, sr=48000, y_noise=noise, stationary=True, prop_decrease=0.9, n_fft=2048)
y = nr.reduce_noise(y=y, sr=48000, stationary=False, prop_decrease=0.5, n_fft=2048)   # second, gentle pass for chatter
with wave.open(clean, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
    wf.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
VOICE = ("highpass=f=85,lowpass=f=9000,equalizer=f=3000:t=q:w=1.2:g=2,"
         "acompressor=threshold=0.08:ratio=2.5:attack=8:release=120:makeup=1.5,loudnorm=I=-16:TP=-1.5")

# ---------------------------------------------------------------- caption overlays (bottom, soft shadow)
FONT = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 54)        # a little bigger: the speech is fast
MAXW, BOTTOM, LH = 1560, 895, 70          # bottom of the frame, just above the channel's news ticker band

def wrap(text):
    words, lines, cur = text.split(), [], ""
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    if d.textlength(text, font=FONT) <= MAXW: return [text]
    best = None                                      # balanced two-line split
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        wa, wb = d.textlength(a, font=FONT), d.textlength(b, font=FONT)
        if max(wa, wb) <= MAXW and (best is None or abs(wa - wb) < best[0]): best = (abs(wa - wb), [a, b])
    return best[1]

def chunks(s, e, text):
    """long sentences shown as two consecutive captions, split at a comma or mid-way"""
    if len(text) <= 70: return [(s, e, text)]
    words = text.split(); n = len(words)
    cand = [k for k in range(2, n - 1) if words[k - 1].endswith(",")]
    k = min(cand, key=lambda k: abs(k - n / 2)) if cand else n // 2
    a, b = " ".join(words[:k]), " ".join(words[k:])
    m = s + (e - s) * len(a) / (len(a) + len(b))
    return [(s, m, a), (m, e, b)]

caps = []
for s, e, t in LINES:
    for cs, ce, ct in chunks(s, e, t):
        caps.append((remap(cs), remap(ce), ct))
for i in range(len(caps) - 1):                      # hold each caption until the next one (no flicker)
    if caps[i + 1][0] - caps[i][1] < 0.6: caps[i] = (caps[i][0], caps[i + 1][0], caps[i][2])

def layer(text):
    img = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    lines = wrap(text); d = ImageDraw.Draw(img)
    y0 = 260 - 20 - LH * len(lines)
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines):
        x = (W - d.textlength(ln, font=FONT)) / 2
        ds.text((x, y0 + i * LH + 3), ln, font=FONT, fill=230)
    blk = Image.new("RGBA", img.size, (0, 0, 0, 0)); blk.putalpha(sh.filter(ImageFilter.GaussianBlur(5)))
    img = Image.alpha_composite(img, blk); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = (W - d.textlength(ln, font=FONT)) / 2
        d.text((x, y0 + i * LH), ln, font=FONT, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 90))
    return np.asarray(img).astype(np.float32) / 255
LAYERS = [layer(t) for _, _, t in caps]

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- follow the speaker: full frame first, then a close view of him
import cv2
SW, SH = 640, 360
INTRO, PUSH = 2.5, 2.2          # full frame for 2.5 s, then a slow push-in onto him
CH = 150                         # close-view height in source pixels (2.4x): him only, not the panel
CW = CH * 16 / 9
fcas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(cut_mp4); det = []
while True:
    ok, f = cap.read()
    if not ok: break
    g = cv2.equalizeHist(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    bx = [b for b in fcas.detectMultiScale(g, 1.08, 4, minSize=(18, 18)) if b[0] + b[2] / 2 > 400 and b[1] < 200]
    det.append(max(bx, key=lambda b: b[2]) if len(bx) else None)          # the speaker is the man on the right
N = len(det)
idx = [k for k in range(N) if det[k] is not None]
raw = np.array([[det[k][0] + det[k][2] / 2, det[k][1] + det[k][3] / 2, det[k][2]] for k in idx], np.float32)
raw = np.stack([np.array([np.median(raw[max(0, k - 4):k + 5, c]) for k in range(len(raw))]) for c in range(3)], 1)  # drop odd detections
track = np.stack([np.interp(np.arange(N), idx, raw[:, c]) for c in range(3)], 1)
# the news camera itself re-frames now and then: let the view jump with those cuts, glide everywhere else
jumps = [0] + [k for k in range(1, N) if abs(track[k, 0] - track[k - 1, 0]) > 14 or abs(track[k, 1] - track[k - 1, 1]) > 14
               or abs(track[k, 2] / track[k - 1, 2] - 1) > 0.2] + [N]
sm = track.copy()
for a, b in zip(jumps, jumps[1:]):
    if b - a > 3:
        for c in range(3):
            seg = np.pad(track[a:b, c], 30, mode="edge")
            k = np.exp(-0.5 * (np.arange(-30, 31) / 10.0) ** 2); k /= k.sum()
            sm[a:b, c] = np.convolve(seg, k, mode="same")[30:-30]
def view(fi):
    cx, cy, _ = sm[min(fi, N - 1)]
    x0 = float(np.clip(cx - CW * 0.5, 0, SW - CW)); y0 = float(np.clip(cy - CH * 0.33, 52, 300 - CH))   # clear of the channel's logo and ticker
    z = ease((fi / FPS - INTRO) / PUSH)
    return x0 * z, y0 * z, SW + (CW - SW) * z, SH + (CH - SH) * z, z

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", cut_mp4, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", clean, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
                        "-crf", "19", "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-af", VOICE, "-ac", "2", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
fi = 0
while True:
    b = dec.stdout.read(SW * SH * 3)
    if len(b) < SW * SH * 3: break
    t = fi / FPS
    src = np.frombuffer(b, np.uint8).reshape(SH, SW, 3)
    x0, y0, vw, vh, z = view(fi)
    sc = W / vw
    M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
    fr = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    fr = fr * 1.4 - cv2.GaussianBlur(fr, (0, 0), 1.6) * 0.4                     # gentle sharpening after the upscale
    CY0 = int(round(BOTTOM + (1000 - BOTTOM) * z)) + 20 - 260                   # above the ticker on the full frame, lower once close
    for (s, e, _), L in zip(caps, LAYERS):
        if s - 0.02 <= t < e:
            a = min(1, (e - t) / 0.12)
            al = L[..., 3:4] * a
            fr[CY0:CY0 + 260] = fr[CY0:CY0 + 260] * (1 - al) + L[..., :3] * 255 * al
            break
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes()); fi += 1
enc.stdin.close(); enc.wait(); dec.wait()
print("wrote", OUT)

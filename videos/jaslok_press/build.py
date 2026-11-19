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
    (72.05, 76.85, "Shayad aapka thirty-five hai, aur koi aur cheez bahut badi hai,"),
    (77.20, 77.98, "jisse aapka risk bada hai,"),
    (78.70, 80.25, "ya phir genetic predisposition se,"),
    (80.25, 82.20, "ya phir aapka Lipoprotein(a) bahut high hai."),
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
KEEP_GAP = 0.14                            # breath left in each cut pause
cuts = []
for s, e in pauses + FILLERS:
    if e - s > KEEP_GAP:
        cuts.append((s + KEEP_GAP / 2, e - KEEP_GAP / 2))
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
NEW_DUR = remap(DUR)
print(f"cuts: {len(merged)}  {DUR:.1f}s -> {NEW_DUR:.1f}s")

# ---------------------------------------------------------------- cut the footage
cut_mp4 = os.path.join(TMP, "cut.mp4")
fc, XF = [], 0.02
for i, (s, e) in enumerate(keep):
    fc.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];"
              f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={XF},afade=t=out:st={max(0, e - s - XF):.3f}:d={XF}[a{i}];")
fc.append("".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a]")
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
CY0 = BOTTOM + 20 - 260

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", cut_mp4, "-vf",
                        f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.35:5:5:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", clean, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
                        "-crf", "19", "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-af", VOICE, "-ac", "2", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
fi = 0
while True:
    b = dec.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    t = fi / FPS
    fr = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.float32)
    for (s, e, _), L in zip(caps, LAYERS):
        if s - 0.02 <= t < e:
            a = min(1, (t - s) / 0.12 + 1) * min(1, (e - t) / 0.12)          # quick soft in/out, no motion
            al = L[..., 3:4] * a
            fr[CY0:CY0 + 260] = fr[CY0:CY0 + 260] * (1 - al) + L[..., :3] * 255 * al
            break
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes()); fi += 1
enc.stdin.close(); enc.wait(); dec.wait()
print("wrote", OUT)

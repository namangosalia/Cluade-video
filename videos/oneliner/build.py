"""Three podcast clips -> one calm, clean vertical short in the style of Naman's reference
(tight close-up on the face, big bold lowercase phrases at chin level, nothing else on screen).

- clip 1 (5_2_1_1): "Okay." and the repeated "that" cut; after "...solve this problem sooner." a short pause fades away
- clip 2 (6_1_1): fades in, "Cardiovascular disease still remains the leading cause of mortality in the world."
- clip 3 (5_2_1_2): starts on "This is the biggest pandemic" (host's "Exactly." and the opening "And" removed)
- not fast: only long pauses are shortened, to a natural breath; soft dips to black between the clips
"""
import json, os, subprocess, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, ".tmp"); os.makedirs(TMP, exist_ok=True); os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
OUT = os.path.join(HERE, "output", "biggest_pandemic_9x16.mp4")
W, H, FPS = 1080, 1920, 25
FONT = os.path.join(REPO, "assets", "fonts", "poppins-latin-800-normal.woff")
def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

parts = [os.path.join(HERE, "raw", f"part{i}.mp4") for i in (1, 2, 3)]
lst = os.path.join(TMP, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
comb = os.path.join(TMP, "combined.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", comb], check=True)
words = json.load(open(os.path.join(HERE, "words.json")))
wav = os.path.join(TMP, "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a16 = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
DUR = len(a16) / 16000
B1 = 28.52; B2 = B1 + 4.394                     # clip joins on the combined timeline

# ---------------------------------------------------------------- edit decision list
# clips (start, end) in combined time, with in-clip cuts; long pauses shortened gently
CLIPS = [(0.42, 28.42), (B1, 32.92), (34.27, 47.32)]
CUTS = [(2.30, 2.84)]                           # repeated "that" ("studies that we have done, that in next decade")
rms = np.array([20 * np.log10(np.sqrt(np.mean(a16[i:i + 400] ** 2)) + 1e-9) for i in range(0, len(a16), 160)])
SIL = min(-30.0, float(np.percentile(rms[rms > -90], 90)) - 20.0)
ends = [wd[1] for wd in words if wd[2].strip().endswith((".", "?", "!"))]
MIN_PAUSE, KEEP, KEEP_LONG = 0.55, 0.40, 0.60   # unhurried: only long gaps shortened
s_ = None
for i, q in enumerate(np.append(rms < SIL, False)):
    if q and s_ is None: s_ = i
    if not q and s_ is not None:
        q0, q1 = s_ / 100, i / 100
        if q1 - q0 >= MIN_PAUSE:
            k = KEEP_LONG if any(e - 0.2 <= q0 <= e + 0.35 for e in ends) else KEEP
            if q1 - q0 > k: CUTS.append((q0 + k / 2, q1 - k / 2))
        s_ = None
pieces = []                                      # (src_start, src_end, clip_index)
for ci, (c0, c1) in enumerate(CLIPS):
    t0 = c0
    for s, e in sorted(x for x in CUTS if c0 < x[0] < c1):
        if s > t0 + 0.04: pieces.append((t0, s, ci))
        t0 = max(t0, e)
    pieces.append((t0, c1, ci))
# timeline: pieces back to back; a held, fading tail after clip 1 and clip 3; a short black gap between clips
TAIL1, GAP, TAIL3 = 0.70, 0.25, 1.2
timeline, t = [], 0.0                            # (out_start, out_end, src_start, clip)
for i, (s, e, ci) in enumerate(pieces):
    if i and pieces[i - 1][2] != ci:
        if pieces[i - 1][2] == 0: t += TAIL1
        t += GAP
    timeline.append((t, t + e - s, s, ci)); t += e - s
BODY = t + TAIL3
def src_at(tn):
    """output time -> (source time or None for black, clip, fade 0..1)"""
    for i, (o0, o1, s, ci) in enumerate(timeline):
        if tn < o1 or i == len(timeline) - 1:
            nxt_clip = timeline[i + 1][3] if i + 1 < len(timeline) else None
            if tn < o0:                                          # between clips: the last frame of the previous clip fading out
                pv = timeline[i - 1]; tail = TAIL1 if pv[3] == 0 else 0.25
                return None, pv[3], 1 - ease((tn - (pv[1] - (0.15 if pv[3] == 1 else 0.0))) / tail)
            src = s + min(tn, o1 - 1 / FPS) - o0
            first = [x for x in timeline if x[3] == ci][0][0]; last = [x for x in timeline if x[3] == ci][-1][1]
            fin = ease((tn - first) / 0.45) if ci > 0 else ease(tn / 0.6)
            tail = TAIL1 if ci == 0 else (TAIL3 if ci == 2 else 0.25)
            fout = 1 - ease((tn - (last - (0.15 if ci == 1 else 0.0))) / tail)
            return src, ci, fin * fout
    return None, 2, 0.0
def out_of(src_t):
    for o0, o1, s, ci in timeline:
        if s <= src_t <= s + (o1 - o0): return o0 + src_t - s
        if src_t < s: return o0
    return timeline[-1][1]
print(f"{len(timeline)} pieces, {BODY:.1f}s (raw {DUR:.1f}s)")

# ---------------------------------------------------------------- close-up framing (face tracked per camera shot)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(comb); SW, SH = int(cap.get(3)), int(cap.get(4))
faces, hists = [], []
while True:
    ok, f = cap.read()
    if not ok: break
    small = cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA)
    hh = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256]); hists.append(cv2.normalize(hh, hh).flatten())
    d = fc.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(36, 36))
    faces.append(max(d, key=lambda b: b[2]) if len(d) else None)
N = len(hists)
shots = [0] + [k for k in range(1, N) if cv2.compareHist(hists[k - 1], hists[k], cv2.HISTCMP_BHATTACHARYYA) > 0.35] + [N]
win = np.zeros((N, 3), np.float32)              # x0, y0, crop height
for a, b in zip(shots, shots[1:]):
    ks = [k for k in range(a, b) if faces[k] is not None]
    if ks:
        cx = np.array([(faces[k][0] + faces[k][2] / 2) * 2 for k in ks], np.float32)
        cy = np.array([(faces[k][1] + faces[k][3] / 2) * 2 for k in ks], np.float32)
        fs = float(np.median([faces[k][2] * 2 for k in ks]))
        med = lambda v: np.array([np.median(v[max(0, j - 6):j + 7]) for j in range(len(v))])
        cx, cy = np.interp(np.arange(a, b), ks, med(cx)), np.interp(np.arange(a, b), ks, med(cy))
        ker = np.exp(-0.5 * (np.arange(-40, 41) / 20.0) ** 2); ker /= ker.sum()
        sm = lambda v: np.convolve(np.pad(v, 40, mode="edge"), ker, mode="same")[40:-40]
        cx, cy = sm(cx), sm(cy)
    else:
        cx, cy, fs = np.full(b - a, SW / 2), np.full(b - a, SH * 0.4), SH / 3
    ch = float(np.clip(fs * 2.7, 440, SH))       # face fills the frame like the reference
    cw = ch * 9 / 16
    win[a:b, 0] = np.clip(cx - cw / 2, 0, SW - cw)
    win[a:b, 1] = np.clip(cy - ch * 0.40, 0, SH - ch)
    win[a:b, 2] = ch

# ---------------------------------------------------------------- captions: short bold lowercase phrases, chin level
CHUNKS = [  # (first word, last word, text)
    (1, 4, "from a number of studies"), (5, 8, "that we have done,"), (10, 12, "in the next decade"), (13, 14, "or so,"),
    (15, 17, "doctors will have"), (18, 19, "two people."), (20, 22, "one would be"), (23, 25, "35 years old."),
    (26, 28, "the other would be"), (29, 31, "75 years old."), (32, 35, "both with acute MI,"), (36, 40, "which is the heart attack."),
    (41, 42, "the doctor, unfortunately,"), (43, 46, "will have to save"), (47, 49, "the 35-year-old"),
    (50, 53, "because he is packed."), (54, 57, "he doesn't have time."), (58, 62, "he'll have to let go"),
    (63, 65, "the 75-year-old"), (66, 68, "if we don't"), (69, 71, "solve this problem"), (72, 72, "sooner."),
    (73, 74, "cardiovascular disease"), (75, 76, "still remains"), (77, 79, "the leading cause"), (80, 84, "of mortality in the world."),
    (87, 88, "this is"), (89, 91, "the biggest pandemic."), (92, 95, "it is not happening."), (96, 98, "there is no"),
    (99, 101, "sudden heart attack."), (102, 106, "it's a build-up process"), (107, 109, "of 10 years,"), (110, 111, "15 years,"),
    (112, 113, "5 years,"), (114, 117, "based on your symptoms."), (118, 120, "and we really"), (121, 123, "must catch that."),
]
F_CAP = ImageFont.truetype(FONT, 84)
dd = ImageDraw.Draw(Image.new("L", (1, 1)))
def cap_layer(text):
    lines, cur = [], ""
    for w_ in text.split():
        if cur and dd.textlength(cur + " " + w_, font=F_CAP) > 900: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur)
    hh = 100 * len(lines) + 60
    img = Image.new("RGBA", (W, hh), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0); ds = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines): ds.text((W / 2, 30 + i * 100 + 4), ln, font=F_CAP, fill=150, anchor="ma")
    s2 = Image.new("RGBA", img.size, (0, 0, 0, 0)); s2.putalpha(sh.filter(ImageFilter.GaussianBlur(10)))
    img = Image.alpha_composite(img, s2); d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines): d.text((W / 2, 30 + i * 100), ln, font=F_CAP, fill=(255, 255, 255, 255), anchor="ma")
    return np.asarray(img).astype(np.float32) / 255
caps = []
for i, (w0, w1, text) in enumerate(CHUNKS):
    s = out_of(words[w0][0] if w0 != 1 else 0.45)
    e = out_of(words[w1][1]) + 0.35
    if i + 1 < len(CHUNKS):
        nx = out_of(words[CHUNKS[i + 1][0]][0])
        if nx - e < 0.5: e = nx
    caps.append((s, e, cap_layer(text)))
CAP_CY = int(H * 0.60)

# ---------------------------------------------------------------- audio: the same edit, gentle fades at the clip ends
cutwav = os.path.join(TMP, "cut.wav")
fl, ins = [], []
for i, (o0, o1, s, ci) in enumerate(timeline):
    last_of_clip = i + 1 == len(timeline) or timeline[i + 1][3] != ci
    first_of_clip = i == 0 or timeline[i - 1][3] != ci
    fo = 0.25 if last_of_clip else 0.015
    fl.append(f"[0:a]atrim={s:.3f}:{s + o1 - o0:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={0.08 if first_of_clip else 0.015},"
              f"afade=t=out:st={max(0, o1 - o0 - fo):.3f}:d={fo},adelay={int(round(o0 * 1000))}:all=1[a{i}];")
mix = "".join(fl) + "".join(f"[a{i}]" for i in range(len(timeline))) + f"amix=inputs={len(timeline)}:normalize=0,apad=whole_dur={BODY:.3f}[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", comb, "-filter_complex", mix, "-map", "[a]", "-ar", "48000", "-t", f"{BODY:.3f}", cutwav], check=True)
VOICE = ("highpass=f=70,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2,highshelf=f=9000:g=1.5,"
         "deesser=i=0.3,acompressor=threshold=0.1:ratio=2.2:attack=8:release=160:makeup=1.4,loudnorm=I=-14:TP=-1:LRA=7")

# ---------------------------------------------------------------- render
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", comb, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", cutwav, "-map", "0:v", "-map", "1:a", "-af", VOICE, "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                        "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{BODY:.3f}", OUT],
                       stdin=subprocess.PIPE)
src_idx, cur = -1, None
def src_frame(k):
    global src_idx, cur
    while src_idx < k:
        b = dec.stdout.read(SW * SH * 3)
        if len(b) < SW * SH * 3: break
        cur = np.frombuffer(b, np.uint8).reshape(SH, SW, 3); src_idx += 1
    return cur
last = np.zeros((H, W, 3), np.float32)
for fi in range(int(round(BODY * FPS))):
    tn = fi / FPS
    src, ci, fade = src_at(tn)
    if src is not None:
        k = min(int(round(src * FPS)), N - 1)
        x0, y0, ch = win[k]; cw = ch * 9 / 16
        sc = W / cw
        M = np.array([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]], np.float32)
        fr = cv2.warpAffine(src_frame(k), M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
        fr = fr * 1.32 - cv2.GaussianBlur(fr, (0, 0), 2.0) * 0.32
        last = fr
    fr = last * fade
    for s, e, L in caps:
        if s - 0.02 <= tn < e:
            p = ease((tn - s) / 0.18); q = 1 - ease((tn - (e - 0.18)) / 0.18)
            a = p * q * min(1.0, fade * 1.5)
            if a <= 0: break
            sc_ = 0.94 + 0.06 * p
            hh, ww = L.shape[:2]
            Ls = cv2.resize(L, (int(ww * sc_), int(hh * sc_)), interpolation=cv2.INTER_AREA) if sc_ < 0.999 else L
            y = CAP_CY - Ls.shape[0] // 2; x = (W - Ls.shape[1]) // 2
            al = Ls[..., 3:4] * a
            fr[y:y + Ls.shape[0], x:x + Ls.shape[1]] = fr[y:y + Ls.shape[0], x:x + Ls.shape[1]] * (1 - al) + Ls[..., :3] * 255 * al
            break
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); dec.terminate()
print("wrote", OUT)

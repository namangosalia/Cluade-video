"""Dr Sunil Thanvi clips -> clean 9:16 sources for engine/reel.py.

The supplied clips are 720x1280 with their own captions burned in at the bottom (y ~930-1280, over a
white-to-black gradient). Burned-in text can't be erased, so each frame is re-framed from the clean area
above it (top 920 px): a 9:16 window that follows the speaker's face slowly, per camera shot.
Audio: the scratchy room/hall noise is reduced (noise profile from the quiet gaps), then the clip's
audio is muxed back. Output: prepped/partN.mp4, 1080x1920, 30 fps.
"""
import os, subprocess, wave
import cv2
import numpy as np
import noisereduce as nr

HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.path.join(HERE, "prepped"); os.makedirs(OUTD, exist_ok=True)
TMP = os.path.join(HERE, ".tmp_prep"); os.makedirs(TMP, exist_ok=True)
OW, OH, FPS = 1080, 1920, 30
CLEAN_H = 920                                    # rows above the burned-in captions
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def clean_audio(src, dst):
    raw = os.path.join(TMP, "raw.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "48000", raw], check=True)
    w = wave.open(raw); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    f = x[: len(x) // 480 * 480].reshape(-1, 480); db = 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-9)
    quiet = db < np.percentile(db, 12) + 3
    noise = f[quiet].reshape(-1) if quiet.sum() > 30 else x[:24000]
    y = nr.reduce_noise(y=x, sr=48000, y_noise=noise, stationary=True, prop_decrease=0.9, n_fft=2048)
    y = nr.reduce_noise(y=y, sr=48000, stationary=False, prop_decrease=0.6, n_fft=2048)
    with wave.open(dst, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
        wf.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())

for name in sorted(os.listdir(os.path.join(HERE, "raw"))):
    src = os.path.join(HERE, "raw", name)
    cap = cv2.VideoCapture(src); SW, SH = int(cap.get(3)), int(cap.get(4))
    faces, hists = [], []
    while True:
        ok, f = cap.read()
        if not ok: break
        top = f[:CLEAN_H]
        small = cv2.resize(top, (SW // 2, CLEAN_H // 2), interpolation=cv2.INTER_AREA)
        h = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256]); hists.append(cv2.normalize(h, h).flatten())
        d = fc.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(30, 30))
        faces.append(max(d, key=lambda b: b[2]) if len(d) else None)
    N = len(hists)
    cuts = [0] + [k for k in range(1, N) if cv2.compareHist(hists[k - 1], hists[k], cv2.HISTCMP_BHATTACHARYYA) > 0.35] + [N]
    CW = int(round(CLEAN_H * 9 / 16 / 2) * 2)
    xs = np.zeros(N, np.float32)
    for a, b in zip(cuts, cuts[1:]):
        ks = [k for k in range(a, b) if faces[k] is not None]
        if ks:
            fx = np.array([(faces[k][0] + faces[k][2] / 2) * 2 for k in ks], np.float32)
            fx = np.array([np.median(fx[max(0, j - 6):j + 7]) for j in range(len(fx))])
            cx = np.interp(np.arange(a, b), ks, fx)
            ker = np.exp(-0.5 * (np.arange(-45, 46) / 22.0) ** 2); ker /= ker.sum()
            cx = np.convolve(np.pad(cx, 45, mode="edge"), ker, mode="same")[45:-45]
        else:
            cx = np.full(b - a, SW / 2)
        xs[a:b] = np.clip(cx - CW / 2, 0, SW - CW)
    print(name, N, "frames; shots at", [round(c / FPS, 1) for c in cuts[1:-1]])
    wav = os.path.join(TMP, name + ".wav"); clean_audio(src, wav)
    out = os.path.join(OUTD, name)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS),
                            "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "12", "-preset", "medium",
                            "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-c:a", "aac", "-b:a", "256k", "-shortest", out], stdin=subprocess.PIPE)
    k = 0
    while True:
        buf = dec.stdout.read(SW * SH * 3)
        if len(buf) < SW * SH * 3: break
        fr = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
        x0 = int(xs[min(k, N - 1)])
        c = cv2.resize(fr[:CLEAN_H, x0:x0 + CW], (OW, OH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        c = c * 1.3 - cv2.GaussianBlur(c, (0, 0), 1.8) * 0.3
        enc.stdin.write(np.clip(c, 0, 255).astype(np.uint8).tobytes()); k += 1
    enc.stdin.close(); enc.wait(); dec.wait()
print("done")

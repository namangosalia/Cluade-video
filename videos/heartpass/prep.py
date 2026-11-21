"""Podcast clips (16:9, multi-camera) -> 9:16 sources for engine/reel.py.

The interview cuts between cameras inside each clip (host, Naman close, Naman wide), so one
global CROP can't work. Each clip is split into shots (frame-difference cuts); inside a shot the
9:16 window is fixed, centred on the median face position of that shot, which reads like a
locked-off vertical camera. Output: prepped/partN.mp4 at 1080x1920 with the original audio.
"""
import os, subprocess, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "prepped"), exist_ok=True)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
OW, OH = 1080, 1920

for name in sorted(os.listdir(os.path.join(HERE, "raw"))):
    src = os.path.join(HERE, "raw", name)
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS); SW, SH = int(cap.get(3)), int(cap.get(4))
    frames, faces, hists = [], [], []
    while True:
        ok, f = cap.read()
        if not ok: break
        small = cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        h = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256])
        hists.append(cv2.normalize(h, h).flatten())
        d = fc.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
        faces.append(max(d, key=lambda b: b[2]) if len(d) else None)
    N = len(hists)
    cuts = [0] + [k for k in range(1, N) if cv2.compareHist(hists[k - 1], hists[k], cv2.HISTCMP_BHATTACHARYYA) > 0.35] + [N]
    CW = int(round(SH * 9 / 16 / 2) * 2)
    xs = np.zeros(N, np.float32)
    for a, b in zip(cuts, cuts[1:]):
        fx = [(faces[k][0] + faces[k][2] / 2) * SW / 640 for k in range(a, b) if faces[k] is not None]
        cx = float(np.median(fx)) if fx else SW / 2
        xs[a:b] = np.clip(cx - CW / 2, 0, SW - CW)
    print(name, f"{N} frames, shots at", [round(c / fps, 2) for c in cuts[1:-1]], "crop x", sorted(set(int(x) for x in xs)))
    # write the cropped, upscaled clip (piped frames) with the original audio
    out = os.path.join(HERE, "prepped", name)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(round(fps)),
                            "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "12", "-preset", "medium",
                            "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-c:a", "aac", "-b:a", "256k", "-shortest", out], stdin=subprocess.PIPE)
    k = 0
    while True:
        buf = dec.stdout.read(SW * SH * 3)
        if len(buf) < SW * SH * 3: break
        fr = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
        x0 = int(xs[min(k, N - 1)])
        crop = cv2.resize(fr[:, x0:x0 + CW], (OW, OH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        crop = crop * 1.35 - cv2.GaussianBlur(crop, (0, 0), 1.8) * 0.35     # offset the upscale softness
        enc.stdin.write(np.clip(crop, 0, 255).astype(np.uint8).tobytes()); k += 1
    enc.stdin.close(); enc.wait(); dec.wait()
print("done")

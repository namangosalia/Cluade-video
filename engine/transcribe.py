#!/usr/bin/env python3
"""Word-level transcript for a video folder: videos/<slug>/words.json (+ words.txt for reading).

    python3 engine/transcribe.py videos/<slug>

Reads SOURCES from videos/<slug>/config.py if it exists, otherwise every .mp4 in
videos/<slug>/raw/ (sorted). Multiple sources are transcribed one by one and joined
with time offsets, matching how engine/reel.py joins them.

The speech model is Whisper 'small' (CTranslate2 int8). Hugging Face is blocked in
this environment, so the model comes from four npm packages
(@skillninja/shortmovie-telop-model-p0..p3) and is reassembled and checksum-verified
into ~/.cache/anginax-whisper the first time.
"""
import glob, hashlib, json, os, runpy, subprocess, sys, tempfile, wave
import numpy as np

MODEL_DIR = os.path.expanduser("~/.cache/anginax-whisper")


def ensure_model():
    if os.path.exists(os.path.join(MODEL_DIR, "model.bin")):
        return MODEL_DIR
    os.makedirs(MODEL_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="whisper-npm-")
    parts = []
    for i in range(4):
        subprocess.run(["npm", "pack", f"@skillninja/shortmovie-telop-model-p{i}", "--silent"], cwd=tmp, check=True,
                       capture_output=True)
    for tgz in sorted(glob.glob(os.path.join(tmp, "*.tgz"))):
        subprocess.run(["tar", "xzf", tgz], cwd=tmp, check=True)
    pkg = os.path.join(tmp, "package")
    for f in os.listdir(pkg):
        if not f.startswith("model.bin.part") and not f.endswith(".tgz"):
            os.replace(os.path.join(pkg, f), os.path.join(MODEL_DIR, f))
    with open(os.path.join(MODEL_DIR, "model.bin"), "wb") as out:
        for i in range(4):
            with open(os.path.join(pkg, f"model.bin.part{i}"), "rb") as fp:
                out.write(fp.read())
    want = open(os.path.join(MODEL_DIR, "model.sha256")).read().split()[0]
    got = hashlib.sha256(open(os.path.join(MODEL_DIR, "model.bin"), "rb").read()).hexdigest()
    if want != got:
        os.remove(os.path.join(MODEL_DIR, "model.bin"))
        sys.exit("whisper model checksum mismatch")
    return MODEL_DIR


def ensure_lib():
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper"], check=True)


def transcribe(path, model):
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", wav], check=True)
    w = wave.open(wav)
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    os.remove(wav)
    segs, _ = model.transcribe(a, word_timestamps=True, vad_filter=False, language="en",
                               initial_prompt="Umm, uh. I'm the founder of AnginaX. Cardiovascular prevention.")
    return [[round(x.start, 2), round(x.end, 2), x.word] for s in segs for x in s.words]


def main():
    vdir = os.path.abspath(sys.argv[1])
    cfg = os.path.join(vdir, "config.py")
    if os.path.exists(cfg):
        srcs = [s if os.path.isabs(s) else os.path.join(vdir, s) for s in runpy.run_path(cfg)["SOURCES"]]
    else:
        srcs = sorted(glob.glob(os.path.join(vdir, "raw", "*.mp4")) + glob.glob(os.path.join(vdir, "raw", "*.mov")))
    if not srcs:
        sys.exit("no sources found")
    ensure_lib()
    from faster_whisper import WhisperModel
    model = WhisperModel(ensure_model(), device="cpu", compute_type="int8")
    words, off = [], 0.0
    for s in srcs:
        ws = transcribe(s, model)
        words += [[round(a + off, 2), round(b + off, 2), t] for a, b, t in ws]
        off += float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                     "stream=duration", "-of", "csv=p=0", s], capture_output=True, text=True).stdout)
        print(f"{os.path.basename(s)}: {len(ws)} words")
    json.dump(words, open(os.path.join(vdir, "words.json"), "w"))
    with open(os.path.join(vdir, "words.txt"), "w") as f:
        f.write(" ".join(f"{i}:{t.strip()}[{a:.2f}]" for i, (a, b, t) in enumerate(words)) + "\n")
    print("wrote", os.path.join(vdir, "words.json"))


if __name__ == "__main__":
    main()

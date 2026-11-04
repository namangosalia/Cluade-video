# Anginax founder reel

- `output/anginax_reel_9x16.mp4`: final 1080x1920 HDR (HLG, HEVC) reel for Instagram Reels, Stories and Meta ads; colours match the iPhone original
- `source/raw.mp4`: original self-recorded clip
- `assets/`: Anginax logo (original + version for dark backgrounds)
- `edit/captions.py`: caption text, timing and highlighted phrases (`[brackets]`)
- `edit/chart_plate.py`: builds the empty-chart plate used to animate the risk curve
- `edit/build.py`: rebuilds the video (cuts pauses, HDR to SDR, grade, captions, logo, end card)

Rebuild: `python3 edit/build.py` (add `--no-captions --out output/clean.mp4` for a caption-free version).

## Video 2: "Why don't we prevent it?"

- `video2/output/anginax_why_prevention_9x16.mp4`: final 1080x1920 HDR reel
- `video2/edit/build.py`: rebuilds it (`python3 video2/edit/build.py`)
- `video2/edit/captions.py`: caption text and highlights; `video2/edit/flow.py`: the five-shot "effort of prevention" sequence; `video2/edit/cine.py`: rendering helpers

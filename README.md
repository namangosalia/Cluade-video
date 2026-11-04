# Anginax founder reel

- `output/anginax_reel_9x16.mp4`: final 1080x1920 reel for Instagram Reels, Stories and Meta ads
- `source/raw.mp4`: original self-recorded clip
- `assets/`: Anginax logo (original + version for dark backgrounds)
- `edit/captions.py`: caption text, timing and highlighted phrases (`[brackets]`)
- `edit/build.py`: rebuilds the video (cuts pauses, HDR to SDR, grade, captions, logo, end card)

Rebuild: `python3 edit/build.py` (add `--no-captions --out output/clean.mp4` for a caption-free version).

# Anginax reel: master prompt

Paste this into the chat with a new raw video. You don't need to write anything else:

> **New Anginax reel. Raw video(s) attached. Follow `MASTER_PROMPT.md` in the repo
> (namangosalia/Cluade-video, branch `claude/anginax-video-edit-5d7pmd`) and deliver the finished reel.**
> *(Optional: "accent cream" for a hopeful message, "add these photos at …", "real B-roll attached for …".)*

Everything below is the brief Claude follows. It records every decision from the first two finished reels:
- `output/anginax_reel_9x16.mp4`, a trust message
- `video2/output/anginax_why_prevention_9x16.mp4`, a problem message

---

## 1. Who and what

- **Speaker:** Naman Gosalia, founder of AnginaX (cardiovascular prevention, at home).
- **Raw material:** self-shot iPhone selfie videos. They're HDR (HLG, BT.2020) and 9:16, usually 506×874 iMovie exports. Sometimes a speech comes in several parts.
- **Output:** a serious, trust-building reel for Instagram Reels, Stories and Meta ads. It should feel like an elegant, senior person addressing a real issue: not hype, not salesy.

## 2. House style (do not change unless asked)

**Picture**
- Naman's colour and skin tone stay exactly as recorded. Never tone-map, grade, vignette, denoise or "beautify" his footage. The pixels stay HLG and the output is HLG HEVC. (Converting to SDR made his skin pale or orange; denoising looked cosmetic.)
- 1080×1920, 30 fps, HEVC 10-bit HLG, `hvc1` tag, faststart. Light sharpening only (to offset the upscale).
- **Open on Naman's face**, in colour. He's on screen for most of the video.
- Varied framing: every cut alternates wide, close and medium (zoom 1.00–1.26) with a slow zoom in or out inside the cut. There's a slow push-in through the closing line.
- A small AnginaX logo sits in the top right (175 px, fully solid, white wordmark with a blue X). It steps aside during photo cards and fades at the end.

**Sound**
- Cut every pause to a breath (0.30 s), with a longer breath (0.62 s) after sentence ends and big lines. Cut "umm/uh" fillers.
- Studio voice chain:
  - high-pass, light denoise
  - +1.5 dB at 130 Hz, −3 dB at 520 Hz
  - +6 dB at 2.9 kHz and 5.2 kHz, +2 dB shelf at 9 kHz
  - de-esser, 3:1 compressor, limiter
- Loudness −14 LUFS, −1 dBTP. No music.

**Captions (the trailer style from Naman's reference video)**
- Captions build word by word as he speaks. Small words are white Inter; the keyword is big **Anton** in cream-gold.
- Numbers are always the keyword: millions, 80%, 59,000, thousands, ₹ amounts.
- Positions rotate around him: bottom-left, bottom-right, bottom-centre, and occasionally top-left for short lines. Keep them low, beside or below the chest, so his face stays clear.
- Lines are long enough to read naturally (not two words at a time), and never so big that they distract from him.
- Spell coined words his way: "default-izing".
- Fix obvious transcription slips (e.g. "pace" → "face", "wreck it" → "tracking it"). Lightly tidy grammar only where it reads better ("why is it happening?").

**Full-screen statements**
- At the biggest lines, Naman's shot greys out and dims (about 0.5 s fades), and big centred Anton text appears line by line on its words. Then his colour comes back.
- Second lines use the accent colour:
  - **red** for problem or alarm messages (video 2)
  - **cream-gold** for hope or trust messages (video 1)
- Numbers count up slowly. A "sequence" keeps one number on screen while labels change under it (59,000 · TODAY → TOMORROW → … → 236,000 IN JUST FOUR DAYS).
- Use about 3–6 per minute: numbers, the central question, and the closing line. Don't put one in the first 3 seconds.

**Cutaways** (his voice continues; captions stay on top)
- **Real B-roll is preferred.** Clips are cover-fitted to 9:16, get a slow push-in, and are colour-matched into HDR so brightness doesn't jump.
- **Photos or press screenshots** become rounded cards with a soft shadow. They swipe slowly over his blurred, dimmed shot.
- **No real footage available:** use the illustrated "one man's experience" sequence (`engine/flow.py`):
  1. **Phone:** leave approved and a hospital appointment
  2. **Hospital:** walking in at dusk
  3. **Queue:** a long line at sample collection
  4. **BusyLobby:** sick patients and a racing clock
  5. **Payment:** a ₹ invoice adding up to thousands
- Never fabricate news headlines or records. Only use press items Naman supplies.

**Ending**
- After the last line: a soft grey dissolve and a white **LEARN MORE** pill button, about 2.8 s. Keep it the same in every reel.
- A teaser or cliffhanger line ("Then what do we do?") becomes the final red statement.

**Other footage (event recordings, LinkedIn/screen recordings, standard colour)**
- Find the lowest point any burned-in captions or labels reach, and crop a 9:16 window (`CROP`) above them.
- Anchor the zooms on the speaker's face (`FOCUS`), with deeper close-ups (`FRAMES` up to 1.45).
- When the speaker stands low in the frame, raise the captions above his head (`CAPTION_BOTTOM`). On bright backgrounds, strengthen the caption shadow (`CAPTION_SHADOW`).
- A light clean-up grade is allowed for these (`SDR_FILTER`, e.g. a highlight curve to tame projector glare). Never grade Naman's iPhone HDR footage.
- Add a name title at the start (`INTRO_LABEL`: "NAMAN GOSALIA / Founder, AnginaX · <event>").
- Cut stutters with `CUT_TIMES`, using the waveform. Always check the cut by transcribing the snippet, because word timestamps around stutters are unreliable.

**Photo + audio (no video)**
- Crop the photo to 9:16 at full quality and hold it static under the audio (`raw/part1.mp4`, made with ffmpeg `-loop 1`). Use `FRAMES = [(1.0, 1.0)]`, with only a very gentle `PUSH_IN` (`PUSH_RANGE` about 1.00–1.06) on the closing line.
- Panel recordings can contain several voices. Use only Naman's part: check the speaker by pitch, and cut with `START_WORD`/`END_WORD`.
- Quiet or boomy room audio gets a per-video `VOICE_CHAIN` (gain, bass cut, presence lift, compression). The pause threshold adapts to the recording's level automatically.
- End on his strongest line, and let it land with `END_HOLD` (about 2 s of silence on the final statement) before the end card.

**Smooth delivery (Naman's preference: no gaps or hesitations)**
- Trim every hesitation gap, not just long ones: `MIN_PAUSE` about 0.16, `PAUSE_KEEP` about 0.12, `PAUSE_KEEP_LONG` about 0.20. After rendering, check that no silence inside the speech exceeds about 0.2 s.
- Whisper usually doesn't transcribe "ahh/uh". Find them by transcribing each sound island separately, and by looking for over-long word stamps. Cut only what is confirmed on the waveform.
- **Intro clip:** to open on Naman walking on stage, set `INTRO_CLIP` (file, ambient level, name `label`). The crop tracks him, the name title goes on the walk, and the clip dissolves into the main picture where the speech starts.

## 3. Workflow (Claude)

1. **Set up.** Create `videos/<slug>/raw/` and put the raw files there in speaking order (part1.mp4, part2.mp4…). Put B-roll in `videos/<slug>/broll/` and images in `videos/<slug>/img/`.
2. **Transcribe.** Run `python3 engine/transcribe.py videos/<slug>`. This writes `words.json` and `words.txt`. The first run fetches the Whisper model via npm, because Hugging Face is blocked here.
3. **Draft.** Run `python3 engine/autoconfig.py videos/<slug> [--accent cream]`. This writes `config.py`.
4. **Edit the config:** this is the editorial pass.
   - Fix transcription slips in the display text.
   - Choose strong keywords: numbers first, then the emotional core of each phrase.
   - Balance positions.
   - Pick the 3–6 statements and write them as two punchy lines.
   - Choose the cutaways (real clips if supplied, otherwise the `flow` shots on the hospital or effort lines).
   - Set `PUSH_IN` on the closing line and `START_WORD` to skip false starts.
5. **Render.** Run `python3 engine/reel.py videos/<slug>/config.py`. A 60 s reel takes about 7–9 minutes.
6. **QA before sending:**
   - Re-transcribe the output: every word must be present, with no clipped word endings.
   - Make a contact sheet of about 15 frames. Check captions don't sit over his face, statements don't overlap captions, cutaways are on the right words, and the opening is his face in colour.
   - `ffprobe`: HEVC, 1080×1920, `arib-std-b67`. Loudness about −14 LUFS.
   - Brightness of cutaways is close to his shots (mean HLG 0.30–0.45 against about 0.45 for him).
7. **Deliver.** Commit to branch `claude/anginax-video-edit-5d7pmd` and push, retrying on transient errors. Send the MP4. Summarise what's on screen when, and list anything that needs Naman (real clips, currency, wording).

Only ask questions when something is genuinely ambiguous: a coined word, a number, the currency, or whether a line should be red or cream. Otherwise decide and deliver.

## 4. Environment notes (cloud session)

- **Blocked:** YouTube, Hugging Face and the stock sites (Pexels, Pixabay, Unsplash, Wikimedia). Real B-roll must be uploaded by Naman, each clip under 30 MB.
- **Available:** npm and PyPI. The Whisper model comes from `@skillninja/shortmovie-telop-model-p0..p3`, and the Anton font is in `assets/fonts/` (from `@fontsource/anton`, OFL).
- To preview HDR frames as SDR stills, use `zscale=t=linear:npl=1000 … tonemap=mobius`. Previews look dimmer than phones show.

## 5. Files

| Path | What |
|---|---|
| `engine/reel.py` | Generic renderer (all the house style above) |
| `engine/transcribe.py`, `engine/autoconfig.py` | Word timings, config draft |
| `engine/trailer_text.py` | Captions and statements typography |
| `engine/flow.py`, `engine/cine.py` | Illustrated hospital sequence, rendering helpers |
| `videos/_template/config.py` | Annotated config reference |
| `edit/`, `video2/edit/` | The two finished reels' own build scripts (kept as-is) |
| `assets/` | Logo (original + on-dark), Anton font, press photos, risk chart |

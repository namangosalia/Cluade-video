"""Innovator Spotlight interview: photo + audio -> reel.

Source: a still photo of Naman speaking (World Heart Federation lanyard) and the panel
audio. raw/part1.mp4 is the photo, cropped 9:16 (x=1150 on the 3503 px original), held
static under the audio. Only Naman's part is used (0-39.6 s): from 40 s a moderator
redirects to other panellists and from 57 s another speaker answers (pitch ~195 Hz
against Naman's ~145-175 Hz). It ends on his question: the uncomfortable truth.
"""
SOURCES = ["raw/part1.mp4"]
OUTPUT = "output/spotlight_interview_9x16.mp4"
ACCENT = "red"
END_CARD = ""
# closing title card on black (replaces Learn More)
END_TITLE = [("THE UNCOMFORTABLE TRUTH", "white"), ("THAT SILENCED THE ROOM AT WHO.", "accent")]
END_TITLE_HOLD = 5.0                # title fully readable for 5 s
END_CTA = "LEARN MORE"              # then fades into Learn More ...
END_CTA_DUR = 2.0                   # ... which stays 2 s and ends the video
START_WORD = 2                      # drop "So, um," -> opens on "A patient walking into..."
END_WORD = 88                       # "...low and middle income countries?"
CUT_TIMES = [(12.95, 14.97),        # "experience different, um, uh, difference" -> "experience difference" (transcription-checked)
             (27.32, 27.68),        # "And now no, we know" -> "And now we know" (syllables from the waveform)
             (26.30, 31.20)]        # drop "And now we know that AI has capability to fix this implementation
                                    # problem." (the solution) -> "...routine in operation. What are the biggest..."
END_HOLD = 1.2                      # the closing question lands, briefly, before the end card

# still image, completely static
FRAMES = [(1.0, 1.0)]
FOCUS = (0.44, 0.42)
PUSH_IN = None                      # no zoom at all
SDR_WHITE = 0.45
SHARPEN = 0.0
# iconic, archival black & white: monochrome, deeper tones, soft edge fall-off, moving film grain
SDR_FILTER = "hue=s=0,curves=all='0/0.03 0.25/0.16 0.5/0.41 0.8/0.75 1/0.90',vignette=PI/6,noise=alls=10:allf=t+u"

# smooth, continuous delivery: every hesitation gap (>= 0.16 s) trimmed to a short breath
MIN_PAUSE = 0.20                    # slightly slower than before: natural breaths, still no hesitation gaps
PAUSE_KEEP, PAUSE_KEEP_LONG = 0.24, 0.45
DRAMATIC_AFTER_WORDS = [26, 36, 43, 54]

# cinema / studio voice for a quiet, boomy panel-room recording
VOICE_CHAIN = [
    "volume=12dB", "highpass=f=85:poles=2", "afftdn=nr=12:nf=-55:tn=1",
    "equalizer=f=170:t=q:w=1.0:g=-6", "equalizer=f=380:t=q:w=1.2:g=-2", "equalizer=f=100:t=q:w=0.9:g=1.5",
    "equalizer=f=2800:t=q:w=0.9:g=7", "equalizer=f=5000:t=q:w=1.0:g=7", "highshelf=f=9000:g=2",
    "deesser=i=0.4:m=0.5:f=0.5",
    "acompressor=threshold=-22dB:ratio=3.5:attack=5:release=150:knee=4:makeup=2",
    "alimiter=limit=0.89:attack=3:release=60:level=disabled",
]

CAPTION_BOTTOM = 1640               # over the dark jacket, below his face
CAPTION_TOP = 240
CAPTION_SHADOW = (14, 2.0, 0.6)
# oratory presentation: photo only, no walk-in, no zoom, no logo; a fixed title at the top
LOGO = False
# speaker identity at the top for the whole video; audio bars beneath it
TITLE = [("NAMAN GOSALIA", "white"), ("Founder, AnginaX  ·  World Heart Forum", "small")]
TITLE_Y = 150
AUDIO_VIS = {"y": 380, "bars": 36, "width": 520, "height": 60}   # audio bars: "an audio clip is playing"

# the places build up as a bold list over the jacket and stay readable for the whole sentence
LISTS = [{"items": [(9, "SINGAPORE", "Mount Elizabeth"), (13, "DELHI", "AIIMS"), (18, "US", "Mayo Clinic"),
                    (25, "EAST AFRICA", "Tribal Health Clinic")],
          "until": 32, "x": 70, "y": 1190, "size": 96, "small_size": 30}]
# hall resonance, added after the cuts so its tails flow naturally over every join
# a filtered hall send under the untouched dry voice (no early slap-back, consonants stay crisp)
POST_CHAIN = ["asplit=2[dry][wet];[wet]highpass=f=250,lowpass=f=5000,"
              "aecho=1.0:1.0:70|130|190|260|340|430:0.35|0.28|0.22|0.16|0.11|0.07,volume=0.30[wv];"
              "[dry][wv]amix=inputs=2:normalize=0,highpass=f=70"]

GROUPS = [
    (2, 9, "A patient walking into Mount Elizabeth in", "B"),
    (32, 37, "a [DIFFERENCE] in his healthcare system.", "B"),
]

STATEMENTS = [
    (37, 44, [("But the underlying gap", "small", 37), ("IS STILL THE SAME.", "white", 41)], "plain"),
    (44, 55, [("cardiovascular prevention is", "small", 46), ("NOT CONTINUOUS.", "white", 49),
              ("NOT LONGITUDINAL.", "white", 51), ("NOT ROUTINE.", "accent", 52)], "plain"),
    (69, 89, [("What are the", "small", 69), ("BIGGEST SYSTEMATIC BARRIERS", "white", 72),
              ("stopping it from happening in", "small", 79), ("LOW & MIDDLE-INCOME COUNTRIES?", "accent", 84)], "plain"),
]

CUTAWAYS = []

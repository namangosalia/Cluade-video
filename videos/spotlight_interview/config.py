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
END_CARD = "LEARN MORE"
START_WORD = 2                      # drop "So, um," -> opens on "A patient walking into..."
END_WORD = 88                       # "...low and middle income countries?"
CUT_TIMES = [(12.95, 14.97),        # "experience different, um, uh, difference" -> "experience difference" (transcription-checked)
             (27.32, 27.68)]        # "And now no, we know" -> "And now we know" (syllables from the waveform)
END_HOLD = 1.2                      # the closing question lands, briefly, before the end card

# still image: no cut-to-cut zoom; a very gentle push-in only on the final question
FRAMES = [(1.0, 1.0)]
FOCUS = (0.44, 0.42)
PUSH_IN = (69, 89)
PUSH_RANGE = (1.0, 1.06)
SDR_WHITE = 0.45
SHARPEN = 0.0

# smooth, continuous delivery: every hesitation gap (>= 0.16 s) trimmed to a short breath
MIN_PAUSE = 0.16
PAUSE_KEEP, PAUSE_KEEP_LONG = 0.12, 0.20
DRAMATIC_AFTER_WORDS = [36, 54, 68]

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
# opens on Naman walking on stage (ambient sound only); the speech starts as the photo appears
INTRO_CLIP = {"file": "raw/walk.mp4", "ambient_lufs": -30, "white": 0.42, "push": 0.05, "dissolve": 0.6,
              "label": ("NAMAN GOSALIA", "Founder, AnginaX  ·  Innovator Spotlight"), "label_y": 1420}

GROUPS = [
    (2, 10, "A patient walking into [MOUNT ELIZABETH] in Singapore,", "BL"),
    (10, 14, "or [AIIMS] in Delhi,", "BR"),
    (14, 19, "or [MAYO CLINIC] in the US,", "BL"),
    (19, 27, "or a [TRIBAL HEALTH CLINIC] in East Africa.", "BR"),
    (27, 37, "He'll experience [DIFFERENCES] in his healthcare system.", "B"),
    (55, 62, "And now we know that [AI]", "BL"),
    (62, 69, "has the capability to fix this [IMPLEMENTATION PROBLEM.]", "BR"),
]

STATEMENTS = [
    (37, 44, [("But the underlying gap", "small", 37), ("IS STILL THE SAME.", "white", 41)], "plain"),
    (44, 55, [("cardiovascular prevention is", "small", 46), ("NOT CONTINUOUS.", "white", 49),
              ("NOT LONGITUDINAL.", "white", 51), ("NOT ROUTINE.", "accent", 52)], "plain"),
    (69, 89, [("What are the", "small", 69), ("BIGGEST SYSTEMATIC BARRIERS", "white", 72),
              ("stopping it from happening in", "small", 79), ("LOW & MIDDLE-INCOME COUNTRIES?", "accent", 84)], "plain"),
]

CUTAWAYS = []

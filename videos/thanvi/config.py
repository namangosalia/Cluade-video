"""Dr Sunil Thanvi (Sr Interventional Cardiologist, Professor & Head of Cardiology) -> AnginaX reel, house style.

Sources are 720x1280 clips with their own captions burned in at the bottom; prep.py re-frames each frame from
the clean area above them (a 9:16 window following his face) and reduces the scratchy hall noise.
Captions here are new (trailer style); AnginaX logo top right; ends on LEARN MORE.
"""
SOURCES = ["prepped/part1.mp4", "prepped/part2.mp4", "prepped/part3.mp4"]
WORDS = "words.json"
OUTPUT = "output/thanvi_ai_heart_care_9x16.mp4"
ACCENT = "cream"                         # hopeful: catching risk early
END_CARD = "LEARN MORE"

CUT_TIMES = [(56.85, 57.90)]             # "it helps us, it suggests us" -> "it suggests us" (transcription-checked)
MIN_PAUSE = 0.16                         # smooth: every hesitation gap trimmed to a short breath
PAUSE_KEEP, PAUSE_KEEP_LONG = 0.14, 0.30

FRAMES = [(1.00, 1.04), (1.08, 1.04), (1.03, 1.07), (1.10, 1.06), (1.04, 1.00)]
FOCUS = (0.5, 0.32)
SDR_WHITE = 0.45
SHARPEN = 0.25
CAPTION_BOTTOM = 1600
CAPTION_SHADOW = (16, 2.4, 0.85)         # bright white stage background
PUSH_IN = (209, 225)

INTRO_LABEL = ("DR SUNIL THANVI", "Sr Interventional Cardiologist  ·  Professor & Head of Cardiology", 0, 19)

GROUPS = [
    (0, 7, "So you used to very [FAMOUSLY] say", "BL"),
    (7, 13, "that [INDIANS] are all [HIGH RISK.]", "BR"),
    (13, 19, "There's [NOBODY] at low risk.", "B"),
    (19, 26, "So you're either at [MILDLY HIGH] risk", "BL"),
    (26, 31, "or at [VERY HIGH RISK.]", "BR"),
    (31, 36, "So we, [TRADITIONALLY,] [GENETICALLY,] [PHENOTYPICALLY,]", "B"),
    (43, 48, "Now, among that [HIGH RISK,]", "BL"),
    (48, 54, "how high [YOUR RISK] is,", "BR"),
    (54, 61, "that we can pick up [VERY EARLY.]", "B"),
    (76, 85, "It helps us to pick up those [RED FLAGS]", "BL"),
    (85, 95, "that we call something which can pick up [VERY EARLY,]", "BR"),
    (95, 104, "to find out if, in future, this [PARTICULAR PERSON]", "B"),
    (104, 112, "must come to me, say, for a [HEALTH CHECKUP,]", "BL"),
    (112, 121, "and we have picked up, for example, [VISCERAL ADIPOSITY.]", "BR"),
    (121, 128, "For the patient, it is [VERY COMMON,]", "BL"),
    (128, 141, "because for him it is a [TYPICAL INDIAN] subset that he belongs to.", "B"),
    (141, 146, "For him, visceral adiposity is [NO BIG DEAL.]", "BR"),
    (146, 156, "But we know now that this [ADIPOSITY] is going to", "BL"),
    (170, 180, "What this particular [PROGRAM] does, in addition to it, is,", "BR"),
    (183, 186, "it [SUGGESTS] us", "B"),
    (186, 192, "if we can do [SOMETHING MORE.]", "BL"),
    (192, 201, "Right? If we missed out, say, a particular [INVESTIGATION,]", "BR"),
    (201, 209, "such as [HS-CRP] or [LIPOPROTEIN(A),]", "B"),
    (209, 214, "or something which can [FURTHER]", "BL"),
]

STATEMENTS = [
    (36, 43, [("WE BELONG TO THE", "white", 36), ("HIGH-RISK POPULATION.", "accent", 40)], "plain"),
    (61, 76, [("WE CAN STOP A", "white", 62), ("HEALTH-CHECKUP PERSON", "white", 68),
              ("FROM BECOMING A", "small", 72), ("CARDIAC PATIENT.", "accent", 74)], "plain"),
    (156, 170, [("IT BUILDS", "white", 156), ("METABOLIC PROBLEMS", "white", 157), ("→ CARDIAC ISSUES.", "accent", 166)], "plain"),
    (214, 225, [("RISK-STRATIFY", "white", 214), ("THE PATIENT", "small", 216),
                ("HIGH OR INTERMEDIATE RISK.", "accent", 220)], "plain"),
]

CUTAWAYS = []

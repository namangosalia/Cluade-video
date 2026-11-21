"""Podcast interview (Gunjan Talks): why Indians get heart attacks -> production reel.

Sources are 16:9 multi-camera podcast clips; prep.py makes 9:16 versions (prepped/partN.mp4) with a fixed
vertical window per camera shot, centred on whoever is speaking. Part 1 is the host's question (kept for
context), parts 2-4 are Naman's answer. Clip edges were cut mid-sentence, so the dangling
"We're not population..." and "So we can't..." are removed. Every cut below was checked by transcribing the join.
"""
SOURCES = ["prepped/part1.mp4", "prepped/part2.mp4", "prepped/part3.mp4", "prepped/part4.mp4"]
WORDS = "words.json"
OUTPUT = "output/heartpass_podcast_9x16.mp4"
ACCENT = "red"                        # the problem: Indians meet the cardiologist in the ICU
END_CARD = "LEARN ABOUT YOUR HEARTPASS"

CUT_TIMES = [(1.90, 7.48),            # host: "Cardiovascular diseases, the rate, uh, of these problems are increasing"
                                      #   -> "The rate of heart attacks is increasing in India specifically."
             (28.27, 28.97),          # "Yeah, yeah."
             (43.72, 46.36),          # "We're not population..." (clip ends mid-thought)
             (70.80, 71.60),          # "We have, uhh, high carb diet"
             (75.02, 75.93),          # false start "So we can't" (across the clip join)
             (82.50, 82.80)]          # drawn-out "in..." before "the ICU"

# smooth, continuous delivery: every hesitation trimmed to a short breath
MIN_PAUSE = 0.16
PAUSE_KEEP, PAUSE_KEEP_LONG = 0.12, 0.22

# picture: already 9:16 and upscaled by prep.py -> gentle zooms only, light sharpening
FRAMES = [(1.00, 1.04), (1.10, 1.06), (1.04, 1.09), (1.12, 1.07), (1.06, 1.02)]
FOCUS = (0.5, 0.30)
SDR_WHITE = 0.45
SHARPEN = 0.2
CAPTION_BOTTOM = 1640                 # over the chest / mic, below the face
CAPTION_SHADOW = (14, 2.0, 0.7)
PUSH_IN = (217, 241)                  # slow push-in through the closing lines

INTRO_LABEL = ("NAMAN GOSALIA", "Founder, AnginaX  ·  Gunjan Talks", 74, 89)

GROUPS = [
    # host's question
    (0, 7, "The rate of [HEART ATTACKS] is increasing", "BL"),
    (16, 19, "in [INDIA,] specifically.", "BR"),
    (19, 32, "However, we know these problems are directly related with things like [OBESITY.]", "B"),
    (32, 45, "And if we look at obesity, this is more in [WESTERN COUNTRIES.]", "BL"),
    (45, 57, "For example, the rate of obesity in the [US] is much higher.", "BR"),
    (57, 69, "Even then, there are not as many [HEART PROBLEMS] as in India.", "BL"),
    (69, 72, "[WHY IS THAT?]", "B"),
    # Naman
    (74, 79, "There are [TWO SECTIONS] here.", "BR"),
    (79, 90, "It's not that only [OBESE PEOPLE] are getting heart attacks, right?", "BL"),
    (103, 110, "Let's talk about [INDIANS] getting heart attacks.", "BL"),
    (110, 120, "Indians are getting heart attacks [MORE,] which is [NOT TRUE,]", "BR"),
    (130, 133, "It's [NOT COSMETIC.]", "BL"),
    (133, 139, "It's more of a [METABOLIC PHENOTYPE.]", "BR"),
    (139, 146, "We have the [LP(A)] marker as [SOUTH ASIANS.]", "BL"),
    (146, 152, "We obviously are [METABOLICALLY ILL] more.", "BR"),
    (152, 164, "And I don't think it's comparable, because they are [ALSO] metabolically ill.", "B"),
    (164, 171, "There are a lot of [DIFFERENT FACTORS.]", "BL"),
    (171, 179, "So we can't really compare [WESTERN VERSUS INDIAN.]", "BR"),
    (179, 185, "But let's talk about [INDIANS] only.", "B"),
    (192, 197, "We have a [HIGH-CARB DIET.]", "BL"),
    (197, 203, "We don't do [PREVENTION] that much.", "BR"),
    (207, 217, "I think that [DELAY] is also one of the aspects:", "B"),
]

STATEMENTS = [
    (90, 103, [("PEOPLE WHO ARE FIT", "white", 95), ("ALSO GET HEART ATTACKS.", "accent", 99)], "plain"),
    (120, 127, [("WE'RE NOT COMPARING", "white", 121), ("APPLES TO APPLES.", "accent", 124)], "plain"),
    (185, 192, [("WE ARE THE", "small", 185), ("DIABETES CAPITAL", "accent", 187), ("OF THE WORLD.", "white", 189)], "plain"),
    (217, 241, [("WE MEET OUR CARDIOLOGIST", "white", 218), ("IN THE ICU.", "accent", 223),
                ("EVEN WITH THE BEST", "white", 233), ("MEDICAL FACILITIES.", "accent", 238)], "plain"),
]

CUTAWAYS = []

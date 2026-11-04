# Trailer-style text, timed to the whisper words in words.json (indexed).
#
# GROUPS: on-speaker captions. (word_from, word_to_exclusive, display, position)
#   display: words; [KEY WORDS] are set big in Anton (cream-gold), others small.
#   position: BL / BR (bottom left/right, beside the body), B (bottom centre), T (top left)
# STATEMENTS: full-screen moments. Naman greys out, lines appear on their words.
#   (word_from, word_to_exclusive, [(line, style, word_index)], kind)
#   style: "num" gold, "white", "red", "small"
GROUPS = [
    (0, 6, "Every year, [MILLIONS] of lives are lost", "BL"),
    (6, 12, "to [HEART ATTACKS] and strokes.", "BR"),
    (18, 22, "Then why is it [HAPPENING?]", "B"),
    (46, 53, "[ALMOST ALL OF US] have heard of someone", "T"),
    (53, 60, "who has suffered a [HEART ATTACK.]", "BR"),
    (60, 65, "So the [BIGGER QUESTION] is,", "BL"),
    (70, 75, "See, for [MOST OF US,]", "BR"),
    (75, 80, "prevention is an [UNWANTED EFFORT.]", "BL"),
    (80, 84, "[TAKING THE DAY OFF,]", "B"),
    (84, 87, "visiting a [HOSPITAL,]", "B"),
    (87, 92, "getting your [BLOOD WORK] done,", "B"),
    (92, 96, "waiting in the [LOBBY,]", "B"),
    (96, 98, "spending [THOUSANDS.]", "B"),
    (98, 106, "And [FEARING] what doctors might come up with.", "BR"),
    (106, 114, "And all that while you're feeling [PERFECTLY FINE.]", "BL"),
    (118, 123, "So why would someone [SPEND]", "BR"),
    (123, 126, "[TIME, MONEY, ENERGY,]", "B"),
    (126, 129, "face the [UNCERTAINTIES]", "BL"),
    # continuation (part 2 words start at index 133)
    (133, 139, "This is neither [PRACTICAL] nor [CONVENIENT,]", "BL"),
    (139, 143, "and I [UNDERSTAND] that.", "BR"),
]

STATEMENTS = [
    (12, 18, [("80%", "num", 12), ("ARE PREVENTABLE", "white", 16)], "pct"),
    (22, 46, [], "daily"),                      # 59,000 today ... 236,000 in four days (animated counter)
    (65, 70, [("WHY CAN'T WE", "white", 65), ("PREVENT THAT?", "red", 68)], "plain"),
    (114, 118, [("NO PAIN.", "white", 114), ("NO SYMPTOMS.", "red", 116)], "plain"),
    (129, 133, [("WHEN NOTHING", "white", 129), ("FEELS WRONG?", "red", 131)], "plain"),
    (143, 148, [("THEN WHAT", "white", 143), ("DO WE DO?", "red", 145)], "plain"),
]

# Quiet runs (start time, original timeline) after which the pause stays longer.
DRAMATIC_AFTER = [4.36, 7.67, 9.36, 14.89, 21.37, 30.95, 44.41, 60.45]

# Caption chunks. Each entry: (first_word_time, last_word_time_end, text)
# Times are in the ORIGINAL video's timeline (from edit/words.json).
# Wrap a phrase in [brackets] to highlight it.
CAPTIONS = [
    (1.05, 2.90, "Prevention is not a [one-time screening.]"),
    (3.88, 5.96, "It's not a full body profile check and you're done."),
    (6.80, 9.40, "It is [lifelong.] It's [longitudinal.]"),
    (10.26, 15.80, "Understanding the exact [cardiovascular biomarkers] you need for your body profile,"),
    (16.62, 19.58, "knowing [your risk,] reducing it to [low risk,]"),
    (20.16, 22.30, "maintaining it, tracking it [over time.]"),
    (22.92, 27.14, "And that's exactly what Anginax is bringing to your doorstep, [at your home.]"),
    (27.14, 30.24, "In fact, by taking care of your own [heart health,]"),
    (30.78, 33.06, "you can become part of a much bigger change,"),
    (33.76, 37.08, "[default-izing] cardiovascular prevention for everyone."),
    (37.70, 41.60, "And that's the conversation Anginax is bringing to [global health.]"),
    (42.04, 44.70, "We don't just want to save lives [in the ICU room,]"),
    (45.42, 48.16, "we want to save lives [while you're at home.]"),
]

# Pauses (gap start in original timeline) that are allowed to breathe longer.
DRAMATIC_AFTER = [2.90, 5.96, 7.86, 9.40, 22.30, 37.08, 44.70]

# ---------------------------------------------------------------- trailer-style text (same system as video 2)
# GROUPS: (word_from, word_to_exclusive, display with [KEY WORDS], position BL/BR/B/T)
GROUPS = [
    (1, 8, "Prevention is not a [ONE-TIME SCREENING.]", "BL"),
    (8, 17, "It's not a full body profile check and [YOU'RE DONE.]", "BR"),
    (22, 27, "Understanding the exact [CARDIOVASCULAR BIOMARKERS]", "B"),
    (27, 33, "you need for your [BODY PROFILE,]", "BR"),
    (33, 36, "knowing [YOUR RISK,]", "B"),
    (36, 41, "reducing it to [LOW RISK,]", "B"),
    (41, 47, "maintaining it, tracking it [OVER TIME.]", "B"),
    (47, 54, "And that's exactly what [ANGINAX] is bringing", "B"),
    (54, 60, "to your doorstep, [AT YOUR HOME.]", "B"),
    (60, 70, "In fact, by taking care of your own [HEART HEALTH,]", "BL"),
    (70, 79, "you can become part of a [MUCH BIGGER CHANGE,]", "BR"),
    (86, 98, "And that's the conversation Anginax is bringing to [GLOBAL HEALTH.]", "B"),
    (98, 109, "We don't just want to save lives [IN THE ICU ROOM,]", "BL"),
]
# STATEMENTS: full-screen moments over the greyed-out speaker. Cream-gold accent (trust, not alarm).
STATEMENTS = [
    (17, 22, [("IT IS LIFELONG.", "white", 17), ("IT'S LONGITUDINAL.", "accent", 20)], "plain"),
    (79, 86, [("which is", "small", 79), ("DEFAULT-IZING", "accent", 81), ("CARDIOVASCULAR PREVENTION", "white", 82),
              ("FOR EVERYONE.", "white", 84)], "plain"),
    (109, 119, [("WE WANT TO SAVE LIVES", "white", 109), ("WHILE YOU'RE AT HOME.", "accent", 114)], "plain"),
]

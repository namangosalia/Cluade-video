# Caption chunks. Each entry: (first_word_time, last_word_time_end, text)
# Times are in the ORIGINAL video's timeline (from edit/words.json).
# Wrap a phrase in [brackets] to highlight it.
CAPTIONS = [
    (1.05, 2.90, "Prevention is not a [one-time screening.]"),
    (3.88, 5.96, "It's not a full body profile check and you're done."),
    (6.80, 7.86, "It is [lifelong.]"),
    (8.68, 9.40, "It's [longitudinal.]"),
    (10.26, 13.32, "Understanding the exact [cardiovascular biomarkers]"),
    (13.32, 15.80, "you need for your body profile,"),
    (16.62, 17.70, "knowing [your risk,]"),
    (18.30, 19.58, "reducing it to [low risk,]"),
    (20.16, 21.02, "maintaining it,"),
    (21.62, 22.30, "tracking it [over time.]"),
    (22.92, 24.94, "And that's exactly what [Anginax] is bringing"),
    (24.94, 27.14, "to your doorstep, [at your home.]"),
    (27.14, 30.24, "In fact, by taking care of your own [heart health,]"),
    (30.78, 33.06, "you can become part of a [much bigger change,]"),
    (33.76, 37.08, "defaultizing cardiovascular prevention [for everyone.]"),
    (37.70, 39.84, "And that's the conversation [Anginax] is bringing"),
    (39.84, 41.60, "to [global health.]"),
    (42.04, 44.70, "We don't just want to save lives [in the ICU room,]"),
    (45.42, 48.16, "we want to save lives [while you're at home.]"),
]

# Pauses (gap start in original timeline) that are allowed to breathe longer.
DRAMATIC_AFTER = [2.90, 5.96, 7.86, 9.40, 22.30, 37.08, 44.70]

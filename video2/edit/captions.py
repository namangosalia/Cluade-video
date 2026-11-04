# Caption chunks: (first_word_time, last_word_end, text), original timeline (edit/words.json).
# [brackets] = gold highlight. Numbers inside a highlight are set in SemiBold.
CAPTIONS = [
    (0.62, 4.42, "Every year, [millions] of lives are lost to heart attacks and strokes."),
    (5.30, 7.84, "[80%] of them are preventable."),
    (8.68, 9.56, "Then why is it happening?"),
    (11.02, 14.86, "[59,000] people will suffer a heart attack today."),
    (16.26, 18.16, "And then [59,000] tomorrow."),
    (18.88, 20.12, "And the day after tomorrow."),
    (20.54, 21.44, "And the day after that."),
    (23.04, 27.62, "Almost all of us have heard of someone who has suffered a heart attack."),
    (27.70, 31.02, "So the bigger question is, [why can't we prevent that?]"),
    (32.34, 36.32, "See, for most of us, prevention is an [unwanted effort.]"),
    (37.10, 41.38, "Taking the day off, visiting a hospital, getting your blood work done,"),
    (42.04, 44.30, "waiting in the lobby, spending [thousands.]"),
    (45.66, 48.04, "And fearing what doctors might come up with."),
    (48.80, 51.16, "And all that while you're feeling [perfectly fine.]"),
    (51.54, 52.78, "[No pain, no symptoms.]"),
    (52.78, 58.20, "So why would someone spend [time, money, energy,]"),
    (58.78, 63.26, "face the uncertainties [when nothing feels wrong?]"),
]

# Quiet runs (start time, original timeline) after which the pause stays longer, for weight.
DRAMATIC_AFTER = [4.36, 7.67, 9.36, 14.89, 21.37, 30.95, 44.41, 60.45]

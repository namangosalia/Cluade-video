"""Reel config - copy this folder to videos/<slug>/ (or let engine/autoconfig.py draft it).

Word indices refer to words.json / words.txt (made by engine/transcribe.py).
Ranges are (from, to_exclusive).
"""
SOURCES = ["raw/part1.mp4"]            # one or more raw recordings, joined in this order
OUTPUT = "output/my_reel_9x16.mp4"
ACCENT = "red"                         # "red" = problem / alarm message, "cream" = hope / trust message
END_CARD = "LEARN MORE"                # grey end card button text ("" = no end card)
START_WORD = 0                         # first word kept (skip a false start like "See,")
PUSH_IN = (40, 52)                     # slow push-in through the closing line (word range) or None
DRAMATIC_AFTER_WORDS = []              # extra longer breaths (sentence ends get one automatically)

# On-speaker captions, word by word. [KEY WORDS] = big Anton in cream-gold; others small white.
# Positions: BL / BR (bottom left / right of the body), B (bottom centre), T (top left, short lines only)
GROUPS = [
    (0, 6, "Every year, [MILLIONS] of lives are lost", "BL"),
    (6, 12, "to [HEART ATTACKS] and strokes.", "BR"),
]

# Full-screen statements over the greyed-out speaker. Lines appear on their word.
# styles: "num" (big cream number, counts up), "white", "accent" (red or cream), "small"
# kinds:  "plain" - lines stack;  "sequence" - first num stays, later white/accent lines replace each
#         other under it, a later "num" line re-counts to a new value (e.g. 59,000 -> 236,000)
STATEMENTS = [
    (12, 18, [("80%", "num", 12), ("ARE PREVENTABLE", "white", 16)], "plain"),
]

# Cutaways (voice continues underneath; captions stay on top):
#   real footage: {"type": "clip", "file": "broll/walking_in.mp4", "from_word": 80, "to_word": 84, "clip_start": 0.0}
#   photo cards : {"type": "photos", "images": ["img/article.jpg", "img/summit.jpg"], "from_word": 86, "to_word": 98}
#   illustrated : {"type": "flow", "shots": [[80, "Phone"], [84, "Hospital"], [87, "Queue"], [92, "BusyLobby"],
#                  [96, "Payment"]], "end_word": 98}
CUTAWAYS = []

"""Air pollution x heart: cinematic slow-motion montage from the 6 keyframe GIFs (img/gifs2/gN_fMM.png).

scene: frames (glob), dur (s), method ("interp" = motion interpolation for small changes,
"dissolve" = slow holds + soft blends for big pose changes), x/y (subject framing in the
9:16 window, fraction of the square frame), push (slow zoom amount), text [(lines, start, end)].
"""
OUTPUT = "output/air_pollution_montage_9x16.mp4"
G = "img/gifs2/"

SCENES = [
    {"frames": G + "g1_f*.png", "dur": 9.4, "method": "dissolve", "x": 0.40, "y": 0.35, "push": 0.10,
     "text": [([("Everyone talks about", "body"), ("AIR POLLUTION.", "big")], 0.2, 4.7),
              ([("And how it affects", "body"), ("OUR LUNGS.", "big")], 4.7, 9.0)]},
    {"frames": G + "g2_f*.png", "dur": 6.2, "method": "dissolve", "x": 0.50, "y": 0.35, "push": 0.09,
     "text": [([("But no one talks about", "body"), ("WHAT TO DO ABOUT IT.", "key")], 0.2, 5.8)]},
    {"frames": G + "g3_f*.png", "dur": 6.8, "method": "dissolve", "x": 0.50, "y": 0.35, "push": 0.09,
     "text": [([("THE FACT:", "red"), ("Air pollution also harms", "body"), ("YOUR HEART", "big"),
                ("and blood vessels,", "body")], 0.2, 6.4)]},
    {"frames": G + "g4_f*.png", "dur": 11.6, "method": "interp", "x": 0.48, "y": 0.30, "push": 0.08,
     "text": [([("increasing the risk of", "body"), ("HEART ATTACKS", "big"), ("AND STROKES", "big")], 0.2, 5.6),
              ([("especially if you have", "body"), ("DIABETES", "key"), ("or", "body"),
                ("HIGH BLOOD PRESSURE.", "key")], 5.6, 11.2)]},
    {"frames": G + "g5_f*.png", "dur": 10.4, "method": "dissolve", "x": 0.42, "y": 0.30, "push": 0.09,
     "text": [([("We can't fix pollution", "body"), ("OVERNIGHT.", "big")], 0.2, 4.8),
              ([("But we can start by understanding", "body"), ("OUR CARDIOVASCULAR HEALTH.", "key")], 4.8, 10.0)]},
    {"frames": G + "g6_f*.png", "dur": 7.0, "method": "interp", "x": 0.50, "y": 0.30, "push": 0.08,
     "text": [([("Know where", "body"), ("YOUR HEART", "big"), ("STANDS TODAY.", "key")], 0.2, 6.6)]},
]
END = ([("LEARN MORE", "big")], 4.0)          # + AnginaX logo

XFADE = 0.9
HAZE = 0.6
PARTICLES = 0.7
GRAIN = 3.5
TEXT_Y = 1470
TEXT_SHADE = 0.55

# To use the original smooth videos (e.g. MP4s exported from Google Flow) instead of the GIF keyframes,
# put them in videos/air_pollution/clips/ and replace each scene's "frames"/"method" with:
#   "video": "clips/01_woman_window.mp4", "slow": 1.6, "start": 0.0
# (slow = slow-motion factor; in-between frames are synthesised from the real motion).

"""Air pollution x heart health: the supplied portraits (8 people in smog), statement after statement.

Portraits come from the uploaded GIF (img/gif/frame_0N.png, 416x463, 256 colours), restored to
img/gif/hq_0N.png (de-banded, upscaled to 1664 px, gently sharpened). The photos already carry
smog, so the added grade and haze are light and faces stay clear; text sits in the lower third.
"""
OUTPUT = "output/air_pollution_people_9x16.mp4"
G = "img/gif/"

SLIDES = [
    (G + "hq_01.png", [("Everyone talks about", "body"), ("AIR POLLUTION.", "big")], 4.6),
    (G + "hq_02.png", [("And how it affects", "body"), ("OUR LUNGS.", "big")], 4.4),
    (G + "hq_03.png", [("But no one talks about", "body"), ("WHAT TO DO ABOUT IT.", "key")], 5.0),
    (G + "hq_04.png", [("THE FACT:", "red"), ("Air pollution also harms", "body"), ("YOUR HEART", "big"),
                       ("and blood vessels,", "body")], 5.8),
    (G + "hq_05.png", [("increasing the risk of", "body"), ("HEART ATTACKS", "big"), ("AND STROKES", "big")], 5.4),
    (G + "hq_06.png", [("especially if you have", "body"), ("DIABETES", "key"), ("or", "body"),
                       ("HIGH BLOOD PRESSURE.", "key")], 6.0),
    (G + "hq_07.png", [("We can't fix pollution", "body"), ("OVERNIGHT.", "big")], 4.6),
    (G + "hq_08.png", [("But we can start by understanding", "body"), ("OUR CARDIOVASCULAR HEALTH.", "key")], 5.6),
    (G + "hq_01.png", [("Know where", "body"), ("YOUR HEART", "big"), ("STANDS TODAY.", "key")], 5.2),
]
END = ([("LEARN MORE", "big")], 4.0)          # + AnginaX logo below

GRADE = 0.45          # photos are already hazy: a light smog grade only
HAZE = 0.55           # drifting smog over them, lighter so faces stay clear
PARTICLES = 0.7
TEXT_Y = 1470         # statements in the lower third, over clothing, not faces
TEXT_SHADE = 0.55
GRAIN = 3.5

"""Health Parliament talk (LinkedIn screen recording) -> production reel.

Source is a 578x570 SDR screen recording of a wide event shot with burned-in captions
(lowest row they reach: y~470) and a 'Health Parliament' label, so the 9:16 crop stops
at y=462 and zooms are anchored on Naman's face, who stands low and right in frame.
Captions therefore sit above his head, over the projection screen.
"""
SOURCES = ["raw/part1.mp4"]
OUTPUT = "output/linkedin_talk_9x16.mp4"
ACCENT = "red"                     # a challenge to policymakers about harm -> red
END_CARD = "LEARN MORE"

CROP = (300, 0, 260, 462)          # 9:16 window around the speaker, above the burned-in captions
FOCUS = (0.63, 0.76)               # his face, as a fraction of the crop
FRAMES = [(1.00, 1.06), (1.38, 1.30), (1.15, 1.22), (1.45, 1.38), (1.06, 1.00), (1.28, 1.36)]
SDR_FILTER = "hqdn3d=1.5:1.5:4:4,curves=all='0/0 0.25/0.18 0.6/0.55 1/0.92',eq=saturation=1.12"   # tame projector glare
CAPTION_SHADOW = (16, 2.4, 0.9)    # captions sit on the bright projection screen
SDR_WHITE = 0.45
SHARPEN = 0.5
CAPTION_BOTTOM = 1220              # captions end above his head
CAPTION_TOP = 240
INTRO_LABEL = ("NAMAN GOSALIA", "Founder, AnginaX  ·  Health Parliament", 0, 11)
INTRO_Y = 330
CUT_TIMES = [(4.99, 5.31)]         # stutter: first "as" in "the world as as much" (checked on the waveform)
PUSH_IN = (173, 185)

GROUPS = [
    (0, 6, "Cardiovascular prevention infrastructure, [BORN IN INDIA]", "BL"),
    (6, 10, "going for [THE WORLD.]", "BR"),
    (11, 17, "As much as the [PUBLIC HEALTH SECTOR]", "B"),
    (17, 23, "requires [PRIVATE,] private also requires [PUBLIC.]", "BL"),
    (23, 29, "See, we all know [AI'S CAPABILITY.]", "BR"),
    (53, 62, "And that's where we all have to [WORK TOGETHER]", "BL"),
    (62, 72, "to make sure it [IMPACTS THE PEOPLE] who need it.", "BR"),
    (72, 78, "So, just [ONE LAST POINT] here,", "B"),
    (78, 91, "I want to mention [ONE MESSAGE] I'm getting from everyone here:", "BL"),
    (91, 93, "[OECD,] [WHO,]", "BR"),
    (93, 96, "[CDSCO] India guidelines,", "BL"),
    (96, 99, "[ETHICS,] [PHYSICIAN-GOVERNED,]", "BR"),
    (99, 103, "embedded into the [HEALTHCARE SYSTEM,]", "B"),
    (103, 106, "[PRIVACY,] data [REPRESENTATION,]", "BL"),
    (106, 108, "[OVERRIDE MECHANISMS,]", "BR"),
    (114, 125, "But I have [ONE QUESTION] for all of you [POLICYMAKERS.]", "B"),
    (125, 136, "If we have the ability today to identify [DISEASE RISK EARLIER,]", "BL"),
    (136, 148, "and if we fail to build systems that do so [EQUITABLY,]", "BR"),
    (154, 164, "because the harm is not only about [DEPLOYING BAD AI.]", "B"),
    (173, 185, "because the systems were [TOO PASSIVE,] or the process was [TOO LONG.]", "BL"),
    (185, 187, "[THANK YOU.]", "BR"),
]

STATEMENTS = [
    (29, 53, [("The world isn't suffering from", "small", 29), ("A LACK OF AI CAPABILITY.", "white", 36),
              ("It's suffering from", "small", 40), ("THE INABILITY TO IMPLEMENT", "accent", 46),
              ("PREVENTION AT SCALE.", "white", 50)], "plain"),
    (108, 114, [("EVERYTHING NEEDS", "white", 108), ("TO BE EMBEDDED.", "white", 110), ("AGREED.", "accent", 113)], "plain"),
    (148, 154, [("ISN'T THAT ALSO", "white", 148), ("AN ETHICAL QUESTION?", "accent", 151)], "plain"),
    (164, 173, [("THE HARM IS ALSO", "white", 164), ("LEAVING DISEASE", "accent", 169), ("UNDETECTED.", "accent", 172)], "plain"),
]

CUTAWAYS = []

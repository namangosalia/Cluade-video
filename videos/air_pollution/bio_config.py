"""Air pollution -> lungs -> blood -> heart: stylised 3D medical animation matched to the script.

SLIDES: (scene, [statement lines], seconds, [label chips])
  chip: (text, x, y, pointer_x, pointer_y, appear_time)  in 1080x1920 output pixels (pointer may be None)
Scenes: inhale, airway, alveoli, blood, artery, pressure, city, heart, scan
"""
OUTPUT = "output/air_pollution_3d_9x16.mp4"

SLIDES = [
    ("inhale", [("Everyone talks about", "body"), ("AIR POLLUTION.", "big")], 4.6,
     [("PM2.5  ·  < 2.5 µm", 70, 380, 760, 940, 1.0)]),
    ("airway", [("And how it affects", "body"), ("OUR LUNGS.", "big")], 4.4,
     [("Fine particles travel deep", 60, 300, None, None, 1.0)]),
    ("alveoli", [("But no one talks about", "body"), ("WHAT TO DO ABOUT IT.", "key")], 5.0,
     [("Lung damage · cancer risk ↑", 60, 250, 300, 660, 2.2)]),
    ("blood", [("THE FACT:", "red"), ("Air pollution also harms", "body"), ("YOUR HEART", "big"),
               ("and blood vessels,", "body")], 5.6,
     [("PM2.5 enters the blood", 60, 230, 520, 760, 1.4)]),
    ("artery", [("increasing the risk of", "body"), ("HEART ATTACKS", "big"), ("AND STROKES", "big")], 5.4,
     [("Inflammation", 640, 300, 760, 900, 0.8), ("Oxidative stress", 70, 300, 420, 640, 1.6),
      ("Plaque narrows the artery", 120, 1180, 760, 960, 2.6)]),
    ("pressure", [("especially if you have", "body"), ("DIABETES", "key"), ("or", "body"),
                  ("HIGH BLOOD PRESSURE.", "key")], 5.8,
     [("High blood pressure", 60, 230, 300, 560, 1.0), ("Blood sugar", 660, 330, 640, 720, 2.0)]),
    ("city", [("We can't fix pollution", "body"), ("OVERNIGHT.", "big")], 4.4, []),
    ("heart", [("But we can start by understanding", "body"), ("OUR CARDIOVASCULAR HEALTH.", "key")], 5.2, []),
    ("scan", [("Know where", "body"), ("YOUR HEART", "big"), ("STANDS TODAY.", "key")], 5.0, []),
]

END = ([("LEARN MORE", "big")], 4.0)          # + AnginaX logo below

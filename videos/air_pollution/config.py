"""Air pollution x heart health: awareness reel (statement after statement).

Photos go in img/ with these names (portrait or landscape; any size >= 1080 px wide is fine).
Until a photo exists, its slot shows a smoggy-skyline placeholder.
Styles: big (white Anton), key (cream Anton), red (red Anton), body (white Inter), small (cream Inter).
"""
OUTPUT = "output/air_pollution_awareness_9x16.mp4"

SLIDES = [
    ("img/01_woman_commuter.jpg", [("Everyone talks about", "body"), ("AIR POLLUTION.", "big")], 4.2),
    ("img/02_older_man.jpg", [("And how it affects", "body"), ("OUR LUNGS.", "big")], 4.0),
    ("img/03_young_man_scooter.jpg", [("But no one talks about", "body"), ("WHAT TO DO ABOUT IT.", "key")], 4.6),
    ("img/04_office_woman.jpg", [("THE FACT:", "red"), ("Air pollution also harms", "body"),
                                  ("YOUR HEART", "big"), ("and blood vessels,", "body")], 5.4),
    ("img/05_office_man.jpg", [("increasing the risk of", "body"), ("HEART ATTACKS", "big"), ("AND STROKES", "big")], 5.0),
    ("img/06_older_woman.jpg", [("especially if you have", "body"), ("DIABETES", "key"), ("or", "body"),
                                 ("HIGH BLOOD PRESSURE.", "key")], 5.6),
    ("img/07_young_woman.jpg", [("We can't fix pollution", "body"), ("OVERNIGHT.", "big")], 4.2),
    ("img/08_family_or_group.jpg", [("But we can start by understanding", "body"), ("OUR CARDIOVASCULAR HEALTH.", "key")], 5.2),
    ("img/09_man_looking_up.jpg", [("Know where", "body"), ("YOUR HEART", "big"), ("STANDS TODAY.", "key")], 4.8),
]

END = ([("LEARN MORE", "big")], 4.0)          # + AnginaX logo below

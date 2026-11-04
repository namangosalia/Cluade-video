"""'The effort of prevention' - an original five-shot illustrated sequence.

A person goes through the whole ordeal: the phone with the leave and the appointment,
walking into a hospital at dusk, a blood sample filling, waiting in a cold lobby,
and the bill. Drawn in sRGB at full resolution with soft light, shallow focus and
slow camera drift, then converted to HLG with film grain (see cine.finish).
Each shot is a callable taking local time t (s) and returning an HLG frame.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import cine

W, H = 1080, 1920
FD = "/usr/share/fonts/opentype/inter/"
EXPOSE = 0.55            # display level of sRGB white for these shots (fraction of 1000 nits)


def font(n, s):
    return cine.font(n, s)


def ease(x):
    return cine.ease(x)


def to_hlg(img, grain=0.010):
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255
    hlg = cine.srgb_to_hlg(a, white=EXPOSE)
    n = cine._rng_grain.standard_normal((H // 2, W // 2), dtype=np.float32) * grain
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)[..., None]
    return np.clip(hlg + n * (0.35 + hlg), 0, 1)


def push(img, t, dur, amount=0.05, fy=0.45, dx=0.0):
    """Slow camera push-in (and optional drift) on a finished PIL frame."""
    u = min(max(t / dur, 0), 1)
    z = 1 + amount * u
    cw, ch = W / z, H / z
    x0 = min(max((W - cw) / 2 + dx * u, 0), W - cw)
    y0 = min(max((H - ch) * fy, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def vgrad(c0, c1, h=H, w=W):
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = np.array(c0, np.float32) * (1 - y) + np.array(c1, np.float32) * y
    return Image.fromarray(np.repeat(arr, w, 1).clip(0, 255).astype(np.uint8), "RGB")


def glow(base, layer, radius, strength=1.0):
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        g.putalpha(g.getchannel("A").point(lambda v: min(255, int(v * strength))))
    base.alpha_composite(g)


def bokeh(img, pts):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for x, y, r, col, a in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (int(255 * a),))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6)))


def person(d, x, y, s, col, walk=None, seated=False):
    """Simple back-view silhouette. (x, y) = feet centre, s = height in px."""
    hw = s * 0.13
    head = s * 0.075
    d.ellipse((x - head, y - s, x + head, y - s + 2 * head), fill=col)
    d.rounded_rectangle((x - hw, y - s + 2 * head + s * 0.01, x + hw, y - s * 0.42), radius=hw * 0.6, fill=col)
    if seated:
        d.rounded_rectangle((x - hw, y - s * 0.48, x + hw * 1.9, y - s * 0.34), radius=s * 0.04, fill=col)
        d.rectangle((x + hw * 1.45, y - s * 0.36, x + hw * 1.9, y), fill=col)
        return
    sw = math.sin(walk or 0) * s * 0.05
    for side, ph in ((-1, sw), (1, -sw)):
        lx = x + side * hw * 0.45
        d.polygon([(lx - hw * 0.38, y - s * 0.43), (lx + hw * 0.38, y - s * 0.43),
                   (lx + ph + hw * 0.30, y), (lx + ph - hw * 0.30, y)], fill=col)


# ============================================================ 1. the phone: day off + appointment
class Phone:
    def __init__(self, dur):
        self.dur = dur
        bg = vgrad((14, 16, 22), (22, 18, 16)).convert("RGBA")
        bokeh(bg, [(860, 380, 70, (255, 176, 90), 0.35), (180, 520, 120, (120, 150, 200), 0.18),
                   (720, 640, 40, (255, 200, 140), 0.25)])
        d = ImageDraw.Draw(bg)
        d.rectangle((0, 1180, W, H), fill=(26, 20, 17, 255))                 # bedside table top
        self.bg = bg

    def __call__(self, t):
        img = self.bg.copy()
        px0, py0, pw, ph = 390, 330, 300, 600
        # light pool of the screen on the table
        pool = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(pool).ellipse((px0 - 140, 1110, px0 + pw + 140, 1320), fill=(150, 170, 220, 120))
        glow(img, pool, 50)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((px0 - 10, py0 - 10, px0 + pw + 10, py0 + ph + 10), 44, fill=(10, 10, 12, 255))
        scr = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        sd = ImageDraw.Draw(scr)
        sd.rounded_rectangle((0, 0, pw - 1, ph - 1), 36, fill=(28, 34, 52, 255))
        sd.text((pw / 2, 70), "7:42", font=font("InterDisplay-Light.otf", 76), fill=(240, 240, 245), anchor="mm")
        sd.text((pw / 2, 125), "Monday", font=font("Inter-Medium.otf", 20), fill=(200, 205, 220), anchor="mm")
        cards = [(0.5, "CALENDAR", "Hospital visit", "Blood tests  ·  9:00 AM"),
                 (1.3, "MAIL", "Leave approved", "Full day off")]
        for i, (tc, app, title, sub) in enumerate(cards):
            a = ease((t - tc) / 0.7)
            if a <= 0:
                continue
            y = 200 + i * 130 + (1 - a) * 30
            card = Image.new("RGBA", (pw - 30, 112), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle((0, 0, pw - 31, 111), 22, fill=(235, 238, 245, int(225 * a)))
            cd.text((18, 14), app, font=font("Inter-SemiBold.otf", 15), fill=(110, 115, 130, int(255 * a)))
            cd.text((18, 38), title, font=font("Inter-SemiBold.otf", 24), fill=(20, 22, 28, int(255 * a)))
            cd.text((18, 72), sub, font=font("Inter-Medium.otf", 19), fill=(60, 64, 75, int(255 * a)))
            scr.alpha_composite(card, (15, int(y)))
        img.alpha_composite(scr, (px0, py0))
        sg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sg).rounded_rectangle((px0, py0, px0 + pw, py0 + ph), 36, fill=(120, 140, 200, 90))
        glow(img, sg, 40)
        return to_hlg(push(img, t, self.dur, 0.06, fy=0.35))


# ============================================================ 2. walking into the hospital at dusk
class Hospital:
    def __init__(self, dur):
        self.dur = dur
        bg = vgrad((24, 30, 44), (70, 56, 52)).convert("RGBA")
        d = ImageDraw.Draw(bg)
        d.rectangle((110, 420, 970, 1260), fill=(30, 32, 38, 255))           # building block
        rng = np.random.default_rng(4)
        win = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        wd = ImageDraw.Draw(win)
        for r in range(9):
            for c in range(8):
                if r >= 7 and 2 <= c <= 5:
                    continue
                lit = rng.uniform() < 0.55
                col = (255, 214, 150) if rng.uniform() < 0.6 else (190, 215, 235)
                x, y = 150 + c * 103, 520 + r * 78
                wd.rectangle((x, y, x + 56, y + 40), fill=col + ((150 if lit else 22),))
        bg.alpha_composite(win)
        glow(bg, win, 10, 0.6)
        door = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(door).rectangle((400, 1080, 680, 1260), fill=(215, 235, 240, 235))
        bg.alpha_composite(door); glow(bg, door, 40, 1.2)
        sign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sign)
        cx, cy, a_, b_ = 540, 470, 46, 14
        sd.rectangle((cx - b_, cy - a_, cx + b_, cy + a_), fill=(235, 70, 60, 255))
        sd.rectangle((cx - a_, cy - b_, cx + a_, cy + b_), fill=(235, 70, 60, 255))
        bg.alpha_composite(sign); glow(bg, sign, 24, 1.4)
        # wet ground with reflections
        ground = Image.new("RGBA", (W, H - 1260), (20, 20, 24, 255))
        refl = bg.crop((0, 1260 - (H - 1260), W, 1260)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(9))
        refl.putalpha(110)
        ground.alpha_composite(refl)
        bg.paste(ground, (0, 1260))
        self.bg = bg

    def __call__(self, t):
        img = self.bg.copy()
        u = min(t / self.dur, 1)
        d = ImageDraw.Draw(img)
        # person walks away from camera toward the doors, getting smaller
        x = 600 - 40 * u
        y = 1760 - 470 * u
        s = 620 - 420 * u
        person(d, x, y, s, (8, 8, 10, 255), walk=t * 5.2)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((x - s * 0.16, y - s * 0.02, x + s * 0.16, y + s * 0.03), fill=(0, 0, 0, 120))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
        return to_hlg(push(img, t, self.dur, 0.05, fy=0.55))


# ============================================================ 3. the blood sample
class Blood:
    def __init__(self, dur):
        self.dur = dur
        bg = vgrad((24, 32, 34), (14, 18, 20)).convert("RGBA")
        bokeh(bg, [(200, 380, 90, (170, 210, 215), 0.20), (820, 300, 120, (210, 230, 235), 0.18),
                   (640, 620, 60, (255, 190, 140), 0.16), (120, 760, 50, (150, 200, 210), 0.15)])
        d = ImageDraw.Draw(bg)
        d.rectangle((0, 1440, W, H), fill=(30, 34, 36, 255))                  # counter
        self.bg = bg

    def tube(self, img, x, fill, cap, label, sharp=True):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        top, bot, w = 1010, 1440, 74
        d.rounded_rectangle((x - w / 2, top, x + w / 2, bot), radius=w / 2, fill=(200, 215, 220, 55),
                            outline=(225, 235, 240, 170), width=3)
        if fill > 0:
            lvl = bot - 8 - (bot - top - 70) * fill
            d.rounded_rectangle((x - w / 2 + 7, lvl, x + w / 2 - 7, bot - 7), radius=w / 2 - 7, fill=(120, 12, 18, 245))
        d.rounded_rectangle((x - w / 2 - 6, top - 46, x + w / 2 + 6, top + 18), radius=10, fill=cap)
        d.rectangle((x - w / 2 + 4, 1160, x + w / 2 - 4, 1250), fill=(240, 240, 236, 220))
        d.text((x, 1205), label, font=font("Inter-SemiBold.otf", 18), fill=(40, 40, 46, 255), anchor="mm")
        d.line((x - w / 2 + 14, top + 40, x - w / 2 + 14, bot - 40), fill=(255, 255, 255, 90), width=4)
        if not sharp:
            lay = lay.filter(ImageFilter.GaussianBlur(9))
        img.alpha_composite(lay)

    def __call__(self, t):
        img = self.bg.copy()
        rack = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(rack).rounded_rectangle((150, 1300, 930, 1360), 10, fill=(70, 78, 82, 255))
        self.tube(img, 260, 1.0, (120, 70, 160, 255), "CBC", sharp=False)
        self.tube(img, 820, 0.9, (220, 190, 70, 255), "HbA1c", sharp=False)
        img.alpha_composite(rack.filter(ImageFilter.GaussianBlur(2)))
        fill = ease((t - 0.3) / max(self.dur - 0.6, 0.5)) * 0.92
        self.tube(img, 540, fill, (200, 50, 50, 255), "LIPID")
        lt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lt).ellipse((300, 900, 780, 1500), fill=(200, 230, 235, 40))
        glow(img, lt, 80)
        return to_hlg(push(img, t, self.dur, 0.06, fy=0.62))


# ============================================================ 4. waiting in the lobby
class Lobby:
    def __init__(self, dur):
        self.dur = dur
        bg = vgrad((40, 46, 48), (30, 33, 34)).convert("RGBA")
        d = ImageDraw.Draw(bg)
        d.rectangle((0, 1380, W, H), fill=(24, 26, 27, 255))                  # floor
        fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(fl).rectangle((140, 0, 940, 40), fill=(225, 240, 238, 255))
        bg.alpha_composite(fl); glow(bg, fl, 70, 1.3)                          # fluorescent strip
        board = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bdd = ImageDraw.Draw(board)
        bdd.rounded_rectangle((90, 230, 420, 380), 12, fill=(10, 12, 14, 255))
        self.board = board
        self.bg = bg

    def __call__(self, t):
        img = self.bg.copy()
        img.alpha_composite(self.board)
        d = ImageDraw.Draw(img)
        token = 41 + int(t / 1.2)
        d.text((255, 270), "NOW SERVING", font=font("Inter-SemiBold.otf", 20), fill=(220, 90, 70, 255), anchor="mm")
        d.text((255, 330), f"A-{token}", font=font("InterDisplay-Medium.otf", 54), fill=(240, 120, 90, 255), anchor="mm")
        # wall clock, minute hand racing (time passing)
        cx, cy, r = 780, 470, 120
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(225, 228, 226, 255), outline=(60, 64, 66, 255), width=8)
        for k in range(12):
            a = k / 12 * 2 * math.pi
            d.line((cx + math.sin(a) * r * 0.82, cy - math.cos(a) * r * 0.82, cx + math.sin(a) * r * 0.92,
                    cy - math.cos(a) * r * 0.92), fill=(50, 52, 54, 255), width=4)
        am = (t * 0.9) * 2 * math.pi
        ah = (2.3 + t * 0.075) * 2 * math.pi / 12 * 12 / 12
        d.line((cx, cy, cx + math.sin(ah) * r * 0.5, cy - math.cos(ah) * r * 0.5), fill=(30, 30, 32, 255), width=9)
        d.line((cx, cy, cx + math.sin(am) * r * 0.78, cy - math.cos(am) * r * 0.78), fill=(30, 30, 32, 255), width=6)
        # row of chairs, one person waiting, head down, phone glow
        for i in range(5):
            x = 170 + i * 185
            d.rounded_rectangle((x - 70, 1180, x + 70, 1240), 12, fill=(18, 20, 22, 255))
            d.rounded_rectangle((x - 70, 1060, x - 50, 1240), 8, fill=(18, 20, 22, 255))
            d.rectangle((x - 60, 1240, x - 50, 1390), fill=(16, 18, 20, 255))
            d.rectangle((x + 50, 1240, x + 60, 1390), fill=(16, 18, 20, 255))
        person(d, 520, 1390, 520, (10, 10, 12, 255), seated=True)
        ph = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ph).ellipse((540, 1010, 620, 1060), fill=(150, 175, 230, 140))
        glow(img, ph, 22)
        return to_hlg(push(img, t, self.dur, 0.05, fy=0.5, dx=-30))


# ============================================================ 5. the bill
class Bill:
    LINES = [("Consultation", 1500), ("Complete blood count", 900), ("Lipid profile", 1800),
             ("HbA1c", 1100), ("ECG", 1200), ("Imaging", 4500)]

    def __init__(self, dur):
        self.dur = dur
        bg = vgrad((22, 19, 17), (14, 12, 11)).convert("RGBA")
        bokeh(bg, [(860, 360, 110, (255, 180, 100), 0.18), (220, 520, 80, (255, 200, 150), 0.12)])
        self.bg = bg

    def __call__(self, t):
        img = self.bg.copy()
        x0, y0, x1, y1 = 200, 1010, 880, 1760
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle((x0 + 14, y0 + 20, x1 + 14, y1 + 20), fill=(0, 0, 0, 150))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
        d = ImageDraw.Draw(img)
        d.rectangle((x0, y0, x1, y1), fill=(232, 228, 218, 255))
        d.text((x0 + 50, y0 + 46), "INVOICE", font=font("Inter-SemiBold.otf", 30), fill=(40, 40, 44, 255))
        d.line((x0 + 50, y0 + 100, x1 - 50, y0 + 100), fill=(160, 156, 148, 255), width=2)
        total = 0
        f = font("Inter-Medium.otf", 26)
        per = max((self.dur - 1.4) / len(self.LINES), 0.25)
        for i, (name, amt) in enumerate(self.LINES):
            a = ease((t - 0.2 - i * per) / 0.4)
            if a <= 0:
                continue
            y = y0 + 130 + i * 62
            col = (50, 50, 56, int(255 * a))
            d.text((x0 + 50, y), name, font=f, fill=col)
            s = f"{amt:,}"
            d.text((x1 - 50 - d.textlength(s, font=f), y), s, font=f, fill=col)
            total += amt * a
        d.line((x0 + 50, y1 - 150, x1 - 50, y1 - 150), fill=(160, 156, 148, 255), width=2)
        d.text((x0 + 50, y1 - 118), "TOTAL", font=font("Inter-SemiBold.otf", 30), fill=(40, 40, 44, 255))
        s = f"{int(round(total)):,}"
        ft = font("InterDisplay-SemiBold.otf", 56)
        d.text((x1 - 50 - d.textlength(s, font=ft), y1 - 132), s, font=ft, fill=(140, 30, 30, 255))
        lamp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lamp).ellipse((150, 900, 950, 1800), fill=(255, 210, 160, 35))
        glow(img, lamp, 90)
        return to_hlg(push(img, t, self.dur, 0.06, fy=0.7))


# ============================================================ the man, and other patients
MAN = (14, 16, 22, 255)          # his dark navy jacket
CROWD = (20, 21, 24, 255)


def figure(img, x, y, s, col=CROWD, pose="stand", rim=None, flip=False):
    """Rim-lit silhouette. pose: stand, sit, sit_slump, cane, child, sling, head_in_hands."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hw, head = s * 0.13, s * 0.075
    bend = 0.0
    if pose == "cane":
        bend = s * 0.06
    if pose in ("sit", "sit_slump", "head_in_hands"):
        hy = y - s * 0.78 + (s * 0.05 if pose != "sit" else 0)
        hx = x + (s * 0.04 if pose != "sit" else 0)
        d.ellipse((hx - head, hy, hx + head, hy + 2 * head), fill=col)
        d.rounded_rectangle((x - hw, hy + 2 * head, x + hw, y - s * 0.36), radius=hw * 0.6, fill=col)
        d.rounded_rectangle((x - hw, y - s * 0.44, x + hw * 2.0, y - s * 0.32), radius=s * 0.04, fill=col)
        d.rectangle((x + hw * 1.5, y - s * 0.36, x + hw * 2.0, y), fill=col)
        if pose == "head_in_hands":
            d.polygon([(x + hw * 0.4, y - s * 0.55), (x + hw * 1.2, y - s * 0.40), (hx + head, hy + head * 1.6)], fill=col)
    elif pose == "child":
        s2 = s * 0.55
        d.ellipse((x - s2 * 0.09, y - s2, x + s2 * 0.09, y - s2 + s2 * 0.18), fill=col)
        d.rounded_rectangle((x - s2 * 0.13, y - s2 * 0.82, x + s2 * 0.13, y - s2 * 0.40), radius=8, fill=col)
        d.rectangle((x - s2 * 0.10, y - s2 * 0.42, x + s2 * 0.10, y), fill=col)
    else:
        d.ellipse((x - head + bend, y - s, x + head + bend, y - s + 2 * head), fill=col)
        d.rounded_rectangle((x - hw + bend * 0.6, y - s + 2 * head + s * 0.01, x + hw + bend * 0.6, y - s * 0.42),
                            radius=hw * 0.6, fill=col)
        for side in (-1, 1):
            lx = x + side * hw * 0.45
            d.polygon([(lx - hw * 0.38, y - s * 0.43), (lx + hw * 0.38, y - s * 0.43),
                       (lx + hw * 0.30, y), (lx - hw * 0.30, y)], fill=col)
        if pose == "cane":
            d.line((x + hw * 1.3, y - s * 0.50, x + hw * 1.6, y), fill=col, width=max(3, int(s * 0.012)))
        if pose == "sling":
            d.rounded_rectangle((x - hw * 0.2, y - s * 0.66, x + hw * 1.1, y - s * 0.56), radius=6, fill=(70, 74, 80, 255))
    if flip:
        lay = lay.transpose(Image.FLIP_LEFT_RIGHT)
    if rim:
        a = lay.getchannel("A")
        edge = Image.new("RGBA", (W, H), rim + (0,))
        shifted = Image.new("L", (W, H), 0)
        shifted.paste(a, (-3, -2))
        e = Image.eval(Image.composite(a, Image.new("L", (W, H), 0), a), lambda v: v)
        rim_a = Image.eval(a, lambda v: v).filter(ImageFilter.MaxFilter(3))
        rim_a = Image.composite(Image.new("L", (W, H), 0), rim_a, shifted.point(lambda v: 255 if v > 128 else 0))
        edge.putalpha(rim_a.filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: int(v * 0.85)))
        img.alpha_composite(lay)
        img.alpha_composite(edge)
    else:
        img.alpha_composite(lay)


# ============================================================ 3b. the long queue for blood tests
class Queue:
    def __init__(self, dur):
        self.dur = dur
        bg = vgrad((44, 50, 52), (30, 33, 35)).convert("RGBA")
        d = ImageDraw.Draw(bg)
        d.rectangle((0, 1420, W, H), fill=(26, 28, 30, 255))
        # counter window at the end of the line, with its lit sign
        win = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        wd = ImageDraw.Draw(win)
        wd.rectangle((560, 640, 960, 1000), fill=(210, 232, 236, 200))
        bg.alpha_composite(win); glow(bg, win, 60, 1.1)
        sign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sign)
        sd.rounded_rectangle((540, 470, 980, 590), 10, fill=(18, 60, 70, 255))
        sd.text((760, 512), "SAMPLE COLLECTION", font=font("Inter-SemiBold.otf", 32), fill=(225, 245, 245, 255), anchor="mm")
        sd.text((760, 556), "BLOOD TESTS", font=font("Inter-Medium.otf", 22), fill=(170, 215, 220, 255), anchor="mm")
        bg.alpha_composite(sign); glow(bg, sign, 18, 0.6)
        fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(fl).rectangle((80, 0, 1000, 36), fill=(225, 240, 238, 255))
        bg.alpha_composite(fl); glow(bg, fl, 70, 1.2)
        self.bg = bg

    def __call__(self, t):
        img = self.bg.copy()
        # a long line receding toward the counter; the man waits at the back, nearest us
        shuffle = 6 * ease(t / self.dur)
        poses = ["stand", "cane", "stand", "sling", "stand", "stand", "stand"]
        for i in range(7):
            k = i / 6
            x = 690 - 520 * (1 - k) ** 1.2 + (shuffle if i < 6 else 0)
            y = 1060 + 560 * (1 - k) ** 1.6
            s = 300 + 640 * (1 - k) ** 1.9
            if i == 0:
                continue
            figure(img, x, y, s, CROWD, poses[i], rim=(140, 170, 175))
        figure(img, 210 + shuffle * 2, 1880, 1040, MAN, "stand", rim=(170, 200, 205))
        return to_hlg(push(img, t, self.dur, 0.05, fy=0.45, dx=10))


# ============================================================ 4b. the busy waiting lobby
class BusyLobby(Lobby):
    def __call__(self, t):
        img = self.bg.copy()
        img.alpha_composite(self.board)
        d = ImageDraw.Draw(img)
        token = 41 + int(t / 1.2)
        d.text((255, 270), "NOW SERVING", font=font("Inter-SemiBold.otf", 20), fill=(220, 90, 70, 255), anchor="mm")
        d.text((255, 330), f"A-{token}", font=font("InterDisplay-Medium.otf", 54), fill=(240, 120, 90, 255), anchor="mm")
        cx, cy, r = 800, 430, 105
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(225, 228, 226, 255), outline=(60, 64, 66, 255), width=8)
        am = (t * 0.9) * 2 * math.pi
        ah = (2.3 + t * 0.075) * 2 * math.pi / 12
        d.line((cx, cy, cx + math.sin(ah) * r * 0.5, cy - math.cos(ah) * r * 0.5), fill=(30, 30, 32, 255), width=9)
        d.line((cx, cy, cx + math.sin(am) * r * 0.78, cy - math.cos(am) * r * 0.78), fill=(30, 30, 32, 255), width=6)
        rim = (150, 175, 180)
        # back row (smaller, further), standing patients, front row with the man
        for i, pose in enumerate(["sit_slump", "sit", "head_in_hands", "sit", "sit_slump", "sit"]):
            figure(img, 110 + i * 175, 1130, 380, CROWD, pose, rim=rim, flip=(i % 2 == 1))
        figure(img, 960, 1250, 560, CROWD, "cane", rim=rim)
        figure(img, 80, 1260, 540, CROWD, "sling", rim=rim)
        figure(img, 170, 1260, 540, CROWD, "child", rim=rim)
        for i, pose in enumerate(["sit", "head_in_hands", None, "sit_slump"]):
            x = 230 + i * 210
            if pose is None:
                continue
            figure(img, x, 1560, 640, CROWD, pose, rim=rim, flip=(i == 3))
        figure(img, 650, 1600, 700, MAN, "sit_slump", rim=(175, 200, 205))
        ph = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ph).ellipse((680, 1100, 760, 1150), fill=(150, 175, 230, 120))
        glow(img, ph, 22)
        return to_hlg(push(img, t, self.dur, 0.05, fy=0.6, dx=-20))


# ============================================================ 5b. paying thousands of rupees
class Payment(Bill):
    LINES = [("Consultation", 1500), ("Complete blood count", 900), ("Lipid profile", 1800),
             ("HbA1c", 1100), ("ECG", 1200), ("Imaging", 4500)]

    def __call__(self, t):
        img = self.bg.copy()
        # billing counter glass and cashier behind it
        counter = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(counter)
        cd.rectangle((0, 160, W, 900), fill=(60, 66, 70, 255))
        cd.rectangle((0, 900, W, 960), fill=(36, 34, 32, 255))
        cd.text((540, 230), "BILLING", font=font("Inter-SemiBold.otf", 40), fill=(225, 230, 232, 255), anchor="mm")
        img.alpha_composite(counter)
        figure(img, 540, 1010, 760, (30, 33, 36, 255), "stand")
        glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glass).rectangle((0, 300, W, 900), fill=(190, 215, 220, 40))
        img.alpha_composite(glass)
        x0, y0, x1, y1 = 200, 1010, 880, 1760
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle((x0 + 14, y0 + 20, x1 + 14, y1 + 20), fill=(0, 0, 0, 150))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
        d = ImageDraw.Draw(img)
        d.rectangle((x0, y0, x1, y1), fill=(232, 228, 218, 255))
        d.text((x0 + 50, y0 + 46), "HOSPITAL INVOICE", font=font("Inter-SemiBold.otf", 30), fill=(40, 40, 44, 255))
        d.line((x0 + 50, y0 + 100, x1 - 50, y0 + 100), fill=(160, 156, 148, 255), width=2)
        total = 0
        f = font("Inter-Medium.otf", 26)
        per = max((self.dur - 1.2) / len(self.LINES), 0.2)
        for i, (name, amt) in enumerate(self.LINES):
            a = ease((t - 0.1 - i * per) / 0.35)
            if a <= 0:
                continue
            y = y0 + 130 + i * 62
            col = (50, 50, 56, int(255 * a))
            d.text((x0 + 50, y), name, font=f, fill=col)
            s = f"₹ {amt:,}"
            d.text((x1 - 50 - d.textlength(s, font=f), y), s, font=f, fill=col)
            total += amt * a
        d.line((x0 + 50, y1 - 150, x1 - 50, y1 - 150), fill=(160, 156, 148, 255), width=2)
        d.text((x0 + 50, y1 - 118), "TOTAL", font=font("Inter-SemiBold.otf", 30), fill=(40, 40, 44, 255))
        s = f"₹ {int(round(total)):,}"
        ft = font("InterDisplay-SemiBold.otf", 56)
        d.text((x1 - 50 - d.textlength(s, font=ft), y1 - 132), s, font=ft, fill=(140, 30, 30, 255))
        # his hand with a card, entering from the right
        u = ease((t - 0.6) / 0.8)
        hand = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hand)
        hx = W + 40 - 360 * u
        hd.rounded_rectangle((hx - 40, 1500, hx + 400, 1640), 50, fill=MAN)
        hd.rounded_rectangle((hx - 150, 1470, hx + 30, 1580), 12, fill=(196, 160, 70, 255))
        img.alpha_composite(hand)
        lamp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lamp).ellipse((150, 900, 950, 1800), fill=(255, 210, 160, 30))
        glow(img, lamp, 90)
        return to_hlg(push(img, t, self.dur, 0.05, fy=0.7))

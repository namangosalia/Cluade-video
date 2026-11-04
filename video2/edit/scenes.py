"""Motion-graphic cutaways for the 'why prevention fails' reel.

Every scene draws a transparent RGBA overlay (sRGB, 1080x1920) for a local time t
(seconds since the scene started). The build script puts it over a backdrop made
from the speaker's own blurred curtain, so colour and light stay continuous.
All times passed in are already on the edited (new) timeline.
"""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FD = "/usr/share/fonts/opentype/inter/"
GOLD = (226, 196, 140)
WHITE = (255, 255, 255)
RED = (214, 86, 74)        # muted, serious red for the heart line


@lru_cache(maxsize=256)
def font(name, size):
    return ImageFont.truetype(FD + name, int(size))


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def tracked(d, cx, y, text, f, fill, track=6, align="center", x=None):
    """Letter-spaced text. Returns width."""
    widths = [d.textlength(ch, font=f) for ch in text]
    tw = sum(widths) + track * (len(text) - 1)
    if align == "center":
        x = cx - tw / 2
    elif align == "right":
        x = cx - tw
    for ch, wd in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill)
        x += wd + track
    return tw


def with_alpha(col, a):
    return col[:3] + (int(255 * max(0, min(1, a))),)


# ------------------------------------------------------------------ heart line (ECG)
def ecg_wave(phase):
    """One beat per unit phase. Returns amplitude (R peak = 1)."""
    p = phase % 1.0
    g = lambda c, w, a: a * math.exp(-0.5 * ((p - c) / w) ** 2)
    return g(0.16, 0.025, 0.10) + g(0.29, 0.007, -0.12) + g(0.31, 0.009, 1.0) + \
        g(0.335, 0.010, -0.28) + g(0.53, 0.040, 0.24)


def ecg_layer(t, y, amp, color, beat=0.9, span=2.6, x0=60, x1=1020, width=4, alpha=1.0, glow=True):
    """Monitor-style sweep: the trace is written left to right, older trace fades."""
    img = Image.new("RGBA", (W, 2 * amp + 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cy = amp + 40
    sweep = (t / (beat * span)) % 1.0
    head = x0 + (x1 - x0) * sweep
    pts = []
    for x in range(x0, x1 + 1, 3):
        # time at which this x was written (most recent pass)
        frac = (x - x0) / (x1 - x0)
        age = (sweep - frac) % 1.0
        tw = t - age * beat * span
        yv = cy - amp * ecg_wave(tw / beat)
        fade = 1.0 - age * 0.85
        pts.append((x, yv, fade))
    for (xa, ya, fa), (xb, yb, fb) in zip(pts, pts[1:]):
        if xa <= head < xb:
            continue   # gap at the write head, like a monitor
        d.line((xa, ya, xb, yb), fill=with_alpha(color, alpha * min(fa, fb)), width=width)
    if glow:
        g = img.filter(ImageFilter.GaussianBlur(7))
        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        out.alpha_composite(g); out.alpha_composite(g); out.alpha_composite(img)
        img = out
    # bright write head
    hy = cy - amp * ecg_wave(t / beat)
    hd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(hd).ellipse((head - 7, hy - 7, head + 7, hy + 7), fill=with_alpha(WHITE, 0.9 * alpha))
    img.alpha_composite(hd.filter(ImageFilter.GaussianBlur(3)))
    return img, y - cy


# ------------------------------------------------------------------ scene: 80% preventable
class Preventable:
    def __init__(self, t_num):
        self.t_num = t_num          # local time the number starts counting

    def __call__(self, t):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        p = ease_out((t - self.t_num) / 1.5) * 0.80
        # ring, supersampled for smooth edges
        S, R, Wd = 2, 250, 16
        ring = Image.new("RGBA", ((2 * R + 40) * S, (2 * R + 40) * S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ring)
        bb = (20 * S, 20 * S, (20 + 2 * R) * S, (20 + 2 * R) * S)
        dr.ellipse(bb, outline=with_alpha(WHITE, 0.14), width=Wd * S)
        if p > 0.001:
            dr.arc(bb, -90, -90 + 360 * p, fill=GOLD + (255,), width=Wd * S)
        ring = ring.resize((2 * R + 40, 2 * R + 40), Image.LANCZOS)
        glow = ring.filter(ImageFilter.GaussianBlur(10))
        cx, cy = W // 2, 560
        a_in = ease(t / 0.4)
        for layer in (glow, ring):
            l = layer.copy()
            l.putalpha(l.getchannel("A").point(lambda v: int(v * a_in)))
            img.alpha_composite(l, (cx - R - 20, cy - R - 20))
        d = ImageDraw.Draw(img)
        n = int(round(p * 100))
        f = font("InterDisplay-SemiBold.otf", 168)
        txt = f"{n}%"
        tw = d.textlength(txt, font=f)
        d.text((cx - tw / 2, cy - 120), txt, font=f, fill=with_alpha(GOLD, a_in))
        a2 = ease((t - self.t_num - 0.7) / 0.5)
        tracked(d, cx, cy + 70, "PREVENTABLE", font("Inter-Medium.otf", 34), with_alpha(WHITE, a2), track=9)
        return img


# ------------------------------------------------------------------ scene: 59,000 a day
def fmt(n):
    return f"{int(round(n)):,}"


class DailyToll:
    """Counter to 59,000 'today', then days stack up with a running total."""

    def __init__(self, t_count, t_today, t_rows, t_row2, t_row3, t_row4):
        self.t_count, self.t_today, self.t_rows = t_count, t_today, t_rows
        self.rows = [("TODAY", t_rows), ("TOMORROW", t_row2), ("THE DAY AFTER", t_row3),
                     ("AND THE DAY AFTER THAT", t_row4)]

    def __call__(self, t):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        a_in = ease(t / 0.4)
        tracked(d, W / 2, 250, "HEART ATTACKS", font("Inter-Medium.otf", 30), with_alpha(WHITE, 0.75 * a_in), track=9)
        d.line((W / 2 - 40, 300, W / 2 + 40, 300), fill=with_alpha(GOLD, 0.8 * a_in), width=2)

        k = ease((t - self.t_rows) / 0.7)      # 0: big counter, 1: rows layout
        # --- big counter (fades/shrinks into row 1)
        if k < 1:
            n = ease_out((t - self.t_count) / 1.6) * 59000
            size = 190 * (1 - k) + 64 * k
            f = font("InterDisplay-SemiBold.otf", size)
            txt = fmt(n)
            tw = d.textlength(txt, font=f)
            x = (W / 2 - tw / 2) * (1 - k) + (980 - tw) * k
            y = 420 * (1 - k) + 352 * k
            d.text((x, y), txt, font=f, fill=with_alpha(GOLD, a_in * (1 - k)))
            a_t = ease((t - self.t_today) / 0.4) * (1 - k)
            tracked(d, W / 2, 650, "TODAY", font("Inter-Medium.otf", 44), with_alpha(WHITE, a_t), track=12)
        # --- rows
        if k > 0:
            total = 0
            fl = font("Inter-Medium.otf", 32)
            fn = font("InterDisplay-SemiBold.otf", 64)
            for i, (label, t0) in enumerate(self.rows):
                a = ease((t - t0) / 0.4) if i else k
                if a <= 0:
                    continue
                y = 352 + i * 112 + (1 - a) * 18
                last = all(t < tn for _, tn in self.rows[i + 1:])
                dim = 1.0 if last else 0.62
                tracked(d, 100, y + 22, label, fl, with_alpha(WHITE, a * dim * 0.9), track=6, align="left", x=100)
                txt = "59,000"
                tw = d.textlength(txt, font=fn)
                d.text((980 - tw, y), txt, font=fn, fill=with_alpha(GOLD, a * (0.75 + 0.25 * dim)))
                if i < 3:
                    d.line((100, y + 96, 980, y + 96), fill=with_alpha(WHITE, 0.10 * a), width=1)
                total += 59000 * ease((t - t0) / 0.5) if i else 59000 * k
            # running total, below the caption band
            if t >= self.rows[1][1] - 0.05:
                a = ease((t - self.rows[1][1]) / 0.4)
                tracked(d, W / 2, 1050, "TOTAL", font("Inter-Medium.otf", 28), with_alpha(WHITE, 0.7 * a), track=9)
                f = font("InterDisplay-SemiBold.otf", 104)
                txt = fmt(total)
                tw = d.textlength(txt, font=f)
                d.text((W / 2 - tw / 2, 1090), txt, font=f, fill=with_alpha(GOLD, a))
        # heart monitor line along the bottom
        e, oy = ecg_layer(t, 1420, 90, RED, alpha=0.85 * a_in)
        img.alpha_composite(e, (0, int(oy)))
        return img


# ------------------------------------------------------------------ scene: the hassle list
def _icon(kind, size=46, col=WHITE):
    S = 4
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 3 * S
    s = size * S
    c = col + (255,)
    if kind == "calendar":
        d.rounded_rectangle((w, 6 * S, s - w, s - w), radius=5 * S, outline=c, width=w)
        d.line((w, 16 * S, s - w, 16 * S), fill=c, width=w)
        for xx in (14, 32):
            d.line((xx * S, 2 * S, xx * S, 10 * S), fill=c, width=w)
        for gy in (24, 33):
            for gx in (13, 23, 33):
                d.ellipse(((gx - 1.6) * S, (gy - 1.6) * S, (gx + 1.6) * S, (gy + 1.6) * S), fill=c)
    elif kind == "hospital":
        d.rounded_rectangle((w, 8 * S, s - w, s - w), radius=3 * S, outline=c, width=w)
        d.line((s / 2, 15 * S, s / 2, 31 * S), fill=c, width=w)
        d.line((s / 2 - 8 * S, 23 * S, s / 2 + 8 * S, 23 * S), fill=c, width=w)
        d.line((10 * S, 8 * S, 23 * S, 2 * S), fill=c, width=w)
        d.line((23 * S, 2 * S, 36 * S, 8 * S), fill=c, width=w)
    elif kind == "drop":
        pts = []
        for i in range(0, 361, 6):
            th = math.radians(i)
            r = 1 - 0.0 * math.cos(th)
            x = math.sin(th) * (1 - math.cos(th)) * 0.5
            y = -math.cos(th)
            pts.append((s / 2 + x * 16 * S * 1.15, s / 2 + 4 * S + y * 18 * S * (0.55 if y < 0 else 0.9)))
        # simple teardrop: circle bottom + pointed top
        d.ellipse((10 * S, 18 * S, 36 * S, 44 * S - w), outline=c, width=w)
        d.line((11 * S, 27 * S, 23 * S, 3 * S), fill=c, width=w)
        d.line((35 * S, 27 * S, 23 * S, 3 * S), fill=c, width=w)
    elif kind == "clock":
        d.ellipse((w, w, s - w, s - w), outline=c, width=w)
        d.line((s / 2, s / 2, s / 2, 11 * S), fill=c, width=w)
        d.line((s / 2, s / 2, 32 * S, s / 2 + 3 * S), fill=c, width=w)
    elif kind == "money":
        d.rounded_rectangle((w, 11 * S, s - w, 35 * S), radius=3 * S, outline=c, width=w)
        d.ellipse((s / 2 - 6 * S, 17 * S, s / 2 + 6 * S, 29 * S), outline=c, width=w)
        d.line((w, 40 * S, s - w, 40 * S), fill=c, width=w)
    return im.resize((size, size), Image.LANCZOS)


class Hassles:
    ITEMS = [("calendar", "Taking the day off", None), ("hospital", "Visiting a hospital", None),
             ("drop", "Getting blood work done", None), ("clock", "Waiting in the lobby", None),
             ("money", "Spending ", "thousands")]

    def __init__(self, times):
        self.times = times
        self.icons = {k: _icon(k) for k, _, _ in self.ITEMS}
        self.icons_gold = {"money": _icon("money", col=GOLD)}

    def __call__(self, t):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        f = font("Inter-Medium.otf", 46)
        fb = font("Inter-SemiBold.otf", 46)
        n_vis = sum(t >= t0 - 0.05 for t0 in self.times)
        for i, ((kind, text, hl), t0) in enumerate(zip(self.ITEMS, self.times)):
            a = ease((t - t0 + 0.05) / 0.38)
            if a <= 0:
                continue
            current = (i == n_vis - 1)
            dim = 1.0 if current else 0.55
            y = 300 + i * 104 + (1 - a) * 16
            x = 150 + (1 - a) * 24
            ic = self.icons_gold.get(kind) if (hl and current) else self.icons[kind]
            l = ic.copy()
            l.putalpha(l.getchannel("A").point(lambda v: int(v * a * dim)))
            img.alpha_composite(l, (int(x), int(y + 4)))
            d.text((x + 80, y), text, font=f, fill=with_alpha(WHITE, a * dim))
            if hl:
                tw = d.textlength(text, font=f)
                d.text((x + 80 + tw, y), hl, font=fb, fill=with_alpha(GOLD, a))
                hw = d.textlength(hl, font=fb)
                d.line((x + 80 + tw, y + 60, x + 80 + tw + hw, y + 60), fill=with_alpha(GOLD, 0.75 * a), width=2)
        return img


# ------------------------------------------------------------------ scene: no pain, no symptoms
class Calm:
    def __init__(self, t_pain, t_sym):
        self.t_pain, self.t_sym = t_pain, t_sym

    def __call__(self, t):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        f = font("Inter-Light.otf", 64)
        a1 = ease((t - self.t_pain) / 0.3)
        a2 = ease((t - self.t_sym) / 0.3)
        tracked(d, W / 2, 330, "NO PAIN.", f, with_alpha(WHITE, a1), track=10)
        tracked(d, W / 2, 420, "NO SYMPTOMS.", f, with_alpha(WHITE, a2), track=10)
        e, oy = ecg_layer(t + 0.4, 660, 110, (235, 232, 225), beat=1.05, alpha=0.9 * ease(t / 0.3))
        img.alpha_composite(e, (0, int(oy)))
        return img

"""Trailer-style typography: word-by-word captions that move around the speaker,
and full-screen statement moments. Everything renders to HLG RGBA regions."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import cine

W, H = 1080, 1920
ANTON = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(
    __import__("os").path.dirname(__import__("os").path.abspath(__file__)))), "assets", "fonts", "Anton-Regular.woff")
INTER = "/usr/share/fonts/opentype/inter/"
CREAM = (240, 214, 158)
WHITE = (255, 255, 255)
RED = (226, 44, 40)
TEXT_WHITE = 0.60        # display level of sRGB white for type (fraction of 1000 nits)

_fc = {}


def anton(size):
    k = ("a", int(size))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(ANTON, int(size))
    return _fc[k]


def inter(size, w="Medium"):
    k = (w, int(size))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(f"{INTER}Inter-{w}.otf", int(size))
    return _fc[k]


def ease(x):
    return cine.ease(x)


def to_hlg_region(img):
    bb = img.getbbox()
    if not bb:
        return None
    reg = np.asarray(img.crop(bb)).astype(np.float32) / 255
    reg[..., :3] = cine.srgb_to_hlg(reg[..., :3], white=TEXT_WHITE)
    return reg, bb[0], bb[1]


def with_shadow(img, radius=10, strength=1.6):
    a = img.getchannel("A")
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, int(v * strength))))
    sh.alpha_composite(img)
    return sh


# ------------------------------------------------------------------ caption groups
def parse(display):
    toks, key = [], False
    for raw in display.split(" "):
        w = raw
        if w.startswith("["):
            key, w = True, w[1:]
        end = "]" in w
        w = w.replace("]", "")
        toks.append((w, key))
        if end:
            key = False
    return toks


class Group:
    def __init__(self, toks, times, pos, t_end):
        self.toks, self.times, self.pos, self.t_end = toks, times, pos, t_end
        self.t0 = times[0] - 0.05
        self.layout = self._layout()

    def _layout(self):
        side = self.pos in ("BL", "BR", "T")
        maxw = 640 if side else 980
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        small = inter(40)
        # runs of consecutive small / key tokens become lines
        runs = []
        for i, (w, k) in enumerate(self.toks):
            if runs and runs[-1][0] == k:
                runs[-1][1].append(i)
            else:
                runs.append([k, [i]])
        lines = []                    # (font, [token idx]) wrapped
        for k, idx in runs:
            if k:
                text = " ".join(self.toks[i][0] for i in idx)
                size = 150
                while size > 70 and d.textlength(text, font=anton(size)) > maxw:
                    size -= 6
                f = anton(size)
            else:
                f = small
            cur = []
            for i in idx:
                trial = " ".join(self.toks[j][0] for j in cur + [i])
                if cur and d.textlength(trial, font=f) > maxw:
                    lines.append((f, cur, k)); cur = []
                cur.append(i)
            lines.append((f, cur, k))
        # positions
        out, y = [], 0
        for f, idx, k in lines:
            asc, desc = f.getmetrics()
            lh = (asc + desc) * (0.92 if k else 1.05)
            words, x = [], 0
            sp = d.textlength(" ", font=f)
            for i in idx:
                wl = d.textlength(self.toks[i][0], font=f)
                words.append((i, x, wl))
                x += wl + sp
            out.append((f, k, y, x - sp, words))
            y += lh
        self.block_h = y
        return out

    def render(self, t):
        if t < self.t0 or t >= self.t_end:
            return None
        a_grp = ease((self.t_end - t) / 0.22)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if self.pos == "T":
            y0 = 210
        else:
            y0 = 1560 - self.block_h
        for f, k, ly, lw, words in self.layout:
            if self.pos in ("BL", "T"):
                lx = 70
            elif self.pos == "BR":
                lx = W - 70 - lw
            else:
                lx = (W - lw) / 2
            for i, x, wl in words:
                tw = self.times[i]
                a = ease((t - tw + 0.04) / 0.18) * a_grp
                if a <= 0:
                    continue
                rise = (1 - ease((t - tw + 0.04) / 0.28)) * (14 if k else 8)
                col = CREAM if k else WHITE
                d.text((lx + x, y0 + ly + rise), self.toks[i][0], font=f, fill=col + (int(255 * a),))
        return to_hlg_region(with_shadow(img))


def build_groups(groups, words, T, body):
    """words: whisper [start, end, text]; T: original->new time map."""
    evs = []
    for gi, (i0, i1, display, pos) in enumerate(groups):
        toks = parse(display)
        n_w = i1 - i0
        times = []
        for j in range(len(toks)):
            wi = i0 + min(int(round(j * n_w / len(toks))), n_w - 1)
            times.append(T(words[wi][0]))
        last_end = T(words[i1 - 1][1]) + 0.6
        nxt = T(words[groups[gi + 1][0]][0]) - 0.06 if gi + 1 < len(groups) else body
        evs.append(Group(toks, times, pos, min(last_end, nxt) if nxt - last_end < 0.5 else last_end))
    return evs


# ------------------------------------------------------------------ statements
STYLE = {"num": (CREAM, 300), "white": (WHITE, 150), "red": (RED, 150), "accent": (CREAM, 150), "small": (WHITE, 42)}


def fmt(n):
    return f"{int(round(n)):,}"


class Statement:
    def __init__(self, lines, times, t0, t1, kind, extra=None):
        self.lines, self.times, self.t0, self.t1, self.kind = lines, times, t0, t1, kind
        self.extra = extra or {}

    def stack(self, items, t):
        """items: [(text, style, t_in, t_out)] -> centred stack render."""
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        vis = []
        for text, style, ti, to in items:
            a = ease((t - ti + 0.05) / 0.35)
            if to is not None:
                a *= 1 - ease((t - to) / 0.35)
            if a > 0:
                vis.append((text, style, a, ti))
        if not vis:
            return None
        blocks = []
        for text, style, a, ti in vis:
            col, size = STYLE[style]
            f = inter(size) if style == "small" else anton(size)
            while style != "small" and d.textlength(text, font=f) > 960:
                size -= 8
                f = anton(size)
            asc, desc = f.getmetrics()
            blocks.append((text, f, col, a, ti, (asc + desc) * (0.95 if style != "small" else 1.3)))
        total = sum(b[5] for b in blocks)
        y = 900 - total / 2
        for text, f, col, a, ti, lh in blocks:
            tw = d.textlength(text, font=f)
            sc_rise = (1 - ease((t - ti + 0.05) / 0.45)) * 18
            d.text(((W - tw) / 2, y + sc_rise), text, font=f, fill=col + (int(255 * a),))
            y += lh
        return to_hlg_region(with_shadow(img, 14, 1.4))

    def render(self, t):
        if t < self.t0 - 0.1 or t >= self.t1 + 0.4:
            return None
        if self.kind == "pct":
            n = int(round(cine.ease_out((t - self.times[0]) / 1.6) * 80))
            return self.stack([(f"{n}%", "num", self.times[0], None), (self.lines[1][0], "white", self.times[1], None)], t)
        if self.kind == "millions":
            m_out = self.times[3] - 0.45          # MILLIONS block leaves as 80% arrives
            items = [(self.lines[0][0], "small", self.times[0], m_out), (self.lines[1][0], "num", self.times[1], m_out),
                     (self.lines[2][0], "small", self.times[2], m_out)]
            t80 = self.times[3]
            if t >= t80 - 0.1:
                n = int(round(cine.ease_out((t - t80) / 1.6) * 80))
                items = [(f"{n}%", "num", t80, None), (self.lines[4][0], "white", self.times[4], None)]
            return self.stack(items, t)
        if self.kind == "daily":
            e = self.extra
            if t < e["total"]:
                n = cine.ease_out((t - e["count"]) / 2.2) * 59000
            else:
                n = 59000 + (236000 - 59000) * cine.ease_out((t - e["total"]) / 1.0)
            labels = e["labels"]
            items = [(fmt(n), "num", e["count"], None)]
            for k, (text, ti) in enumerate(labels):
                to = labels[k + 1][1] - 0.3 if k + 1 < len(labels) else None
                items.append((text, "white" if k < len(labels) - 1 else "red", ti, to))
            # number + the newest label only (each label fades in under the number)
            started = [it for it in items[1:] if it[2] - 0.05 <= t]
            cur = [(started[-1][0], started[-1][1], started[-1][2], None)] if started else []
            return self.stack([items[0]] + cur, t)
        items = [(text, style, ti, None) for (text, style, _), ti in zip(self.lines, self.times)]
        return self.stack(items, t)


def build_statements(stmts, words, T):
    out = []
    for i0, i1, lines, kind in stmts:
        t0 = T(words[i0][0]) - 0.15
        t1 = T(words[i1 - 1][1]) + 0.35
        times = [T(words[wi][0]) for _, _, wi in lines]
        extra = None
        if kind == "daily":
            W_ = lambda k: T(words[k][0])
            extra = {"count": W_(22), "total": W_(45) + 0.35,
                     "labels": [("TODAY", W_(30)), ("TOMORROW", W_(35)), ("THE DAY AFTER", W_(38)),
                                ("AND THE DAY AFTER THAT", W_(43)), ("IN JUST FOUR DAYS", W_(45) + 0.45)]}
            t1 = W_(45) + 1.45
        out.append(Statement(lines, times, t0, t1, kind, extra))
    return out

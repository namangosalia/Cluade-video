#!/usr/bin/env python3
"""Draft videos/<slug>/config.py from videos/<slug>/words.json.

    python3 engine/autoconfig.py videos/<slug> [--accent red|cream] [--force]

The draft follows the house style (MASTER_PROMPT.md): phrase groups with a big
Anton keyword, positions rotating around the speaker, full-screen statements for
numbers and short questions, sentence-end breaths. It is a starting point: Claude
reviews it (keywords, statement wording, cutaways) before rendering.
"""
import glob, json, os, re, sys

FILLERS = {"um", "umm", "uh", "uhh", "hmm", "erm", "ah", "mm"}
STOP = set("""a an the and or but so to of in on at for with by from as is are was were be been being it its it's
this that these those i we you he she they them us our your my me him her their there here then than which who whom
what when where why how not no nor do does did done have has had will would can can't could should may might must
just also very really all some any each every much many more most one into about over up down out off own same
see like get got getting while yet""".split())
NUMWORDS = {"million", "millions", "billion", "billions", "thousand", "thousands", "hundred", "hundreds", "percent", "lakh",
            "lakhs", "crore", "crores"}
CUTAWAY_HINTS = {"hospital": "Hospital", "lobby": "BusyLobby", "waiting": "BusyLobby", "queue": "Queue", "line": "Queue",
                 "blood": "Queue", "test": "Queue", "tests": "Queue", "spending": "Payment", "pay": "Payment",
                 "paying": "Payment", "bill": "Payment", "thousands": "Payment", "rupees": "Payment",
                 "day": "Phone", "leave": "Phone", "appointment": "Phone"}


def norm(t):
    return re.sub(r"[^\w%,'-]", "", t.strip()).lower()


def is_num(t):
    return bool(re.search(r"\d", t)) or norm(t).strip(",.") in NUMWORDS


def display_tokens(words, i0, i1):
    """Merge whisper fragments ('59' ',000' / '80' '%') into display tokens: [(text, first_index)]."""
    out = []
    for i in range(i0, i1):
        t = words[i][2].strip()
        if out and (re.match(r"^[,.]?\d", t) and re.search(r"\d$", out[-1][0]) or t in ("%",)) and not t[0].isalpha():
            out[-1] = (out[-1][0] + t, out[-1][1])
        else:
            out.append((t, i))
    return out


def phrases(words):
    """Split into phrases at punctuation / pauses / 8 words. Yields (i0, i1, ends_sentence)."""
    i0 = 0
    for i, (s, e, t) in enumerate(words):
        nxt_gap = words[i + 1][0] - e if i + 1 < len(words) else 9
        end_sent = t.strip().endswith((".", "?", "!"))
        brk = end_sent or t.strip().endswith(",") or nxt_gap > 0.45 or (i - i0 + 1) >= 8
        if brk:
            yield i0, i + 1, end_sent
            i0 = i + 1
    if i0 < len(words):
        yield i0, len(words), True


def sentences(words):
    i0 = 0
    for i, (_, _, t) in enumerate(words):
        if t.strip().endswith((".", "?", "!")) or i == len(words) - 1:
            yield i0, i + 1
            i0 = i + 1


def group_text(toks):
    """Pick the key words of a phrase and return display text with [KEY] markup."""
    texts = [t for t, _ in toks]
    keys = [k for k, t in enumerate(texts) if is_num(t)]
    if keys:
        k0 = keys[0]
        k1 = k0 + 1 if k0 + 1 < len(texts) and norm(texts[k0 + 1]).strip(",.?") not in STOP else k0
        span = (k0, k1)
    else:
        content = [k for k, t in enumerate(texts) if norm(t).strip(",.?!") not in STOP]
        if not content:
            span = (len(texts) - 1, len(texts) - 1)
        else:
            k1 = content[-1]
            k0 = k1 - 1 if (k1 - 1) in content else k1
            span = (k0, k1)
    out = []
    for k, t in enumerate(texts):
        if span[0] <= k <= span[1]:
            t = t.upper()
            if k == span[0]:
                t = "[" + t
            if k == span[1]:
                t = t + "]"
        out.append(t)
    return " ".join(out)


def main():
    vdir = os.path.abspath(sys.argv[1])
    accent = "red"
    if "--accent" in sys.argv:
        accent = sys.argv[sys.argv.index("--accent") + 1]
    cfg = os.path.join(vdir, "config.py")
    if os.path.exists(cfg) and "--force" not in sys.argv:
        sys.exit(f"{cfg} exists (use --force to overwrite)")
    words = json.load(open(os.path.join(vdir, "words.json")))
    fill = {i for i, w in enumerate(words) if norm(w[2]).strip(",.") in FILLERS}

    # statements: number sentences and short questions, spaced >= 7 s apart, not in the first 3 s
    stmts, last_t = [], -99
    for i0, i1 in sentences(words):
        idx = [i for i in range(i0, i1) if i not in fill]
        if not idx:
            continue
        toks = display_tokens(words, idx[0], idx[-1] + 1)
        texts = [t for t, _ in toks]
        has_num = any(re.search(r"\d", t) for t in texts)
        question = texts[-1].endswith("?") and len(texts) <= 8
        t0 = words[idx[0]][0]
        if not (has_num or question) or t0 < 3.0 or t0 - last_t < 7.0 or len(texts) > 12:
            continue
        if has_num:
            k = next(k for k, t in enumerate(texts) if re.search(r"\d", t))
            rest = [t for t in texts[k + 1:] if norm(t).strip(",.?") not in STOP][:3]
            lines = [(texts[k].strip(",."), "num", toks[k][1])]
            if rest:
                wi = next(i for t, i in toks if t == rest[0])
                lines.append((" ".join(rest).upper().strip(",."), "white", wi))
        else:
            half = max(1, len(toks) // 2)
            lines = [(" ".join(t for t, _ in toks[:half]).upper(), "white", toks[0][1]),
                     (" ".join(t for t, _ in toks[half:]).upper(), "accent", toks[half][1])]
        stmts.append((idx[0], idx[-1] + 1, lines))
        last_t = t0
    in_stmt = {i for a, b, _ in stmts for i in range(a, b)}

    groups, cyc, hints = [], ["BL", "BR", "B", "BL", "BR", "T"], []
    for i0, i1, _ in phrases(words):
        idx = [i for i in range(i0, i1) if i not in fill and i not in in_stmt]
        if not idx:
            continue
        # keep contiguous runs only
        runs, cur = [], [idx[0]]
        for i in idx[1:]:
            if i == cur[-1] + 1:
                cur.append(i)
            else:
                runs.append(cur); cur = [i]
        runs.append(cur)
        for r in runs:
            toks = display_tokens(words, r[0], r[-1] + 1)
            pos = cyc[len(groups) % len(cyc)]
            if pos == "T" and len(toks) > 5:
                pos = "B"
            groups.append((r[0], r[-1] + 1, group_text(toks), pos))
            for t, i in toks:
                h = CUTAWAY_HINTS.get(norm(t).strip(",.?"))
                if h:
                    hints.append((i, h, t))

    srcs = sorted(os.path.relpath(p, vdir) for p in glob.glob(os.path.join(vdir, "raw", "*.mp4")) +
                  glob.glob(os.path.join(vdir, "raw", "*.mov")))
    L = []
    L.append(f'"""Draft by engine/autoconfig.py - review keywords, statements and cutaways before rendering."""')
    L.append(f"SOURCES = {srcs!r}")
    L.append(f'OUTPUT = "output/{os.path.basename(vdir)}_9x16.mp4"')
    L.append(f'ACCENT = "{accent}"          # "red" for problem / alarm videos, "cream" for hope / trust videos')
    L.append('END_CARD = "LEARN MORE"')
    L.append(f"PUSH_IN = ({groups[-1][0] if groups else 0}, {len(words)})   # slow push-in through the closing line")
    L.append("\n# (word_from, word_to_exclusive, display with [KEY WORDS], position BL/BR/B/T)")
    L.append("GROUPS = [")
    for a, b, txt, pos in groups:
        L.append(f"    ({a}, {b}, {txt!r}, {pos!r}),")
    L.append("]\n")
    L.append("# full-screen moments over the greyed-out speaker: (from, to_excl, [(text, style, word)], kind)")
    L.append("# styles: num (counts up), white, accent, small.  kinds: plain | sequence")
    L.append("STATEMENTS = [")
    for a, b, lines in stmts:
        L.append(f"    ({a}, {b}, {lines!r}, 'plain'),")
    L.append("]\n")
    L.append("# cutaways: {'type': 'clip', 'file': 'broll/x.mp4', 'from_word': i, 'to_word': j}")
    L.append("#           {'type': 'photos', 'images': ['img/a.jpg'], 'from_word': i, 'to_word': j}")
    L.append("#           {'type': 'flow', 'shots': [[i, 'Phone'], [j, 'Hospital'], ...], 'end_word': k}")
    for i, h, t in hints:
        L.append(f"# suggestion: word {i} '{t.strip()}' -> {h} shot / real clip")
    L.append("CUTAWAYS = []")
    open(cfg, "w").write("\n".join(L) + "\n")
    print(f"wrote {cfg}: {len(groups)} groups, {len(stmts)} statements, {len(hints)} cutaway hints")


if __name__ == "__main__":
    main()

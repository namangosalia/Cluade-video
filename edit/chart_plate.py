"""Build an 'empty chart' plate of the longitudinal chart image plus curve geometry.

Outputs (cached next to the source image's name in edit/.tmp):
  clean  - the image with curve, fill, dashed guides, markers and pills removed
  curve_y - per-column y of the curve line (image px), for the animated head
"""
import numpy as np
from PIL import Image, ImageFilter

# plot area (image px) - inside the axes
PX0, PX1, PY0, PY1 = 841, 1628, 316, 597
PILLS = [(866, 320, 1018, 373), (1062, 401, 1262, 456), (1313, 464, 1468, 519)]   # High, Moderate, Low
DOTS_X = [895, 1068, 1324]


def build(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    H, W = im.shape[:2]
    lum = im @ np.array([0.3, 0.59, 0.11], np.float32)

    # curve: brightest pixel per column inside the plot area, ignoring pills
    pill_mask = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in PILLS:
        pill_mask[y0:y1, x0:x1] = True
    curve_y = np.full(W, np.nan, np.float32)
    for x in range(PX0, PX1):
        col = lum[PY0:PY1, x].copy()
        col[pill_mask[PY0:PY1, x]] = -1
        if col.max() > 120:
            curve_y[x] = PY0 + int(np.argmax(col))
    # smooth + fill gaps
    xs = np.arange(W)
    ok = ~np.isnan(curve_y)
    curve_y = np.interp(xs, xs[ok], curve_y[ok]).astype(np.float32)
    k = np.ones(9) / 9
    curve_y = np.convolve(np.pad(curve_y, 4, mode="edge"), k, mode="valid").astype(np.float32)

    # region to replace: curve band + everything under it down to the x axis, pills, arrow head
    yy = np.arange(H)[:, None]
    rep = np.zeros((H, W), bool)
    band = (yy >= curve_y[None, :] - 24) & (yy < PY1 - 1)
    rep[:, PX0:PX1] = band[:, PX0:PX1]
    rep[PY0:PY1, :] &= True
    rep |= pill_mask
    rep[PY0:PY1, 1590:PX1] |= (np.abs(yy[PY0:PY1] - curve_y[1600]) < 22)   # arrow head
    rep[:PY0] = False
    rep[PY1:] = False

    # local background estimate by normalised convolution (masked blur) on a 1/4-res
    # grid, so it follows the panel's soft lighting; then a little grain is added back.
    valid = (~rep) & (lum < 95)
    valid[:, 832:847] &= ~((np.arange(H) >= PY0 - 20) & (np.arange(H) <= PY1 + 4))[:, None].repeat(15, 1)
    valid[PY1 - 2:PY1 + 4, :] = False                                   # x axis line
    s4 = (W // 4, H // 4)
    def down(a):
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize(s4, Image.BOX)).astype(np.float64)
    def gblur(a, sig):
        r = int(3 * sig); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2); k /= k.sum()
        a = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, "valid"), 0, a)
        return np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, "valid"), 1, a)
    w = down(valid.astype(np.float32))
    est = np.zeros((H, W, 3), np.float32)
    # multi-scale: fine estimate where clean pixels are near, wider ones where they are not
    dens = {sg: gblur(w, sg) for sg in (5, 12, 28, 60)}
    for c in range(3):
        d = down(im[..., c] * valid)
        acc, wacc = np.zeros_like(w), np.zeros_like(w)
        remaining = np.ones_like(w)
        for sg in (5, 12, 28, 60):
            den = dens[sg]
            val = gblur(d, sg) / (den + 1e-6)
            conf = np.clip(den / 0.25, 0, 1) * remaining
            acc += val * conf; wacc += conf
            remaining = remaining * (1 - np.clip(den / 0.25, 0, 1))
        est[..., c] = np.asarray(Image.fromarray((acc / (wacc + 1e-6)).astype(np.float32), "F").resize((W, H), Image.BICUBIC))
    rng = np.random.default_rng(1)
    est += rng.normal(0, 1.0, est.shape).astype(np.float32)
    m = Image.fromarray((rep * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))
    m = (np.asarray(m).astype(np.float32) / 255)[..., None]
    clean = im * (1 - m) + est * m
    return im / 255, np.clip(clean, 0, 255) / 255, curve_y


if __name__ == "__main__":
    import sys
    orig, clean, cy = build(sys.argv[1])
    Image.fromarray((clean * 255).astype(np.uint8)).crop((760, 310, 1640, 680)).save(sys.argv[2])
    print("curve y at dots:", [round(float(cy[x])) for x in DOTS_X], "end", round(float(cy[1600])))

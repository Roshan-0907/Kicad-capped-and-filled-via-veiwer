"""Generate the toolbar icons in pofv_via_3d/icons (needs Pillow).

apply: a solid via pad under solder mask (no hole).
clear: an open via (pad with drilled hole).
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "pofv_via_3d" / "icons"

THEMES = {
    # mask green, copper-under-mask, bare copper, hole, outline
    "light": ("#2f6b3a", "#6f8a3a", "#c98a2e", "#202020", "#1b3d22"),
    "dark": ("#4f9a5c", "#9db55a", "#e0a548", "#101010", "#cfe8d3"),
}


def draw(kind: str, theme: str, size: int) -> Image.Image:
    mask, masked_cu, bare_cu, hole, outline = THEMES[theme]
    s = size / 24.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def circle(r, fill, width=0, color=None):
        c = size / 2
        d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=fill,
                  outline=color, width=max(1, round(width * s)) if color else 0)

    # Square of solder mask behind the via
    d.rounded_rectangle((1 * s, 1 * s, 23 * s, 23 * s), radius=4 * s, fill=mask,
                        outline=outline, width=max(1, round(1 * s)))

    if kind in ("mark", "unmark"):
        ring = "#ff9020"
        circle(7, ring)
        circle(4.5, masked_cu if kind == "mark" else mask)
    elif kind == "apply":
        # Via pad under mask, no hole: same shade as a masked trace
        d.rectangle((10.5 * s, 1 * s, 13.5 * s, 12 * s), fill=masked_cu)
        circle(7, masked_cu)
    else:
        # Bare annular ring with an open hole
        circle(7, bare_cu)
        circle(3.5, hole)

    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    for kind in ("apply", "clear", "unmark"):
        for theme in THEMES:
            for size in (24, 48):
                draw(kind, theme, size).save(OUT / f"{kind}_{theme}_{size}.png")


if __name__ == "__main__":
    main()

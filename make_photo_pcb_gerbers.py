from __future__ import annotations

import math
import zipfile
from pathlib import Path

from PIL import Image


SRC = Path("PCB_黑白双色_保细节抖动版.png")
OUT = Path("photo_pcb_gerber")

CARD_W = 85.60
CARD_H = 52.54
CORNER_R = 3.18
EDGE_CLEARANCE = 0.30
COPPER_INSET = 0.25


def gcoord(mm: float) -> str:
    return str(int(round(mm * 1_000_000)))


def xy(x: float, y: float) -> str:
    return f"X{gcoord(x)}Y{gcoord(y)}"


def header() -> list[str]:
    return [
        "G04 Generated decorative ENIG photo PCB card*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
        "%ADD10C,0.010*%",
        "G54D10*",
    ]


def footer() -> list[str]:
    return ["M02*"]


def rounded_points(x0: float, y0: float, x1: float, y1: float, r: float, steps: int = 16) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    centers = [
        (x1 - r, y1 - r, 0, 90),
        (x0 + r, y1 - r, 90, 180),
        (x0 + r, y0 + r, 180, 270),
        (x1 - r, y0 + r, 270, 360),
    ]
    for cx, cy, a0, a1 in centers:
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def write_region(path: Path, pts: list[tuple[float, float]]) -> None:
    lines = header()
    lines.append("G36*")
    lines.append(f"{xy(*pts[0])}D02*")
    for p in pts[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append(f"{xy(*pts[0])}D01*")
    lines.append("G37*")
    lines.extend(footer())
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def write_outline(path: Path) -> None:
    lines = [
        "G04 Board outline, 85.60 x 52.54 mm CR80 rounded card*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
        "%ADD10C,0.100*%",
        "G54D10*",
    ]
    pts = rounded_points(0, 0, CARD_W, CARD_H, CORNER_R, 20)
    lines.append(f"{xy(*pts[0])}D02*")
    for p in pts[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append(f"{xy(*pts[0])}D01*")
    lines.extend(footer())
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def inside_rounded_card(x: float, y: float, margin: float) -> bool:
    x0, y0 = margin, margin
    x1, y1 = CARD_W - margin, CARD_H - margin
    r = max(0.0, CORNER_R - margin)
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    if x < x0 + r and y < y0 + r:
        return (x - (x0 + r)) ** 2 + (y - (y0 + r)) ** 2 <= r**2
    if x > x1 - r and y < y0 + r:
        return (x - (x1 - r)) ** 2 + (y - (y0 + r)) ** 2 <= r**2
    if x < x0 + r and y > y1 - r:
        return (x - (x0 + r)) ** 2 + (y - (y1 - r)) ** 2 <= r**2
    if x > x1 - r and y > y1 - r:
        return (x - (x1 - r)) ** 2 + (y - (y1 - r)) ** 2 <= r**2
    return True


def write_mask_from_bitmap(path: Path, img: Image.Image) -> tuple[int, int]:
    bw = img.convert("L")
    w, h = bw.size
    px_w = CARD_W / w
    px_h = CARD_H / h
    pix = bw.load()
    lines = header()
    runs = 0

    for row in range(h):
        y_top = CARD_H - row * px_h
        y_bot = CARD_H - (row + 1) * px_h
        y_mid = (y_top + y_bot) / 2
        col = 0
        while col < w:
            while col < w:
                x_mid = (col + 0.5) * px_w
                if pix[col, row] > 127 and inside_rounded_card(x_mid, y_mid, EDGE_CLEARANCE):
                    break
                col += 1
            if col >= w:
                break
            start = col
            while col < w:
                x_mid = (col + 0.5) * px_w
                if pix[col, row] <= 127 or not inside_rounded_card(x_mid, y_mid, EDGE_CLEARANCE):
                    break
                col += 1
            end = col
            x0 = start * px_w
            x1 = end * px_w
            lines.extend(
                [
                    "G36*",
                    f"{xy(x0, y_bot)}D02*",
                    f"{xy(x1, y_bot)}D01*",
                    f"{xy(x1, y_top)}D01*",
                    f"{xy(x0, y_top)}D01*",
                    f"{xy(x0, y_bot)}D01*",
                    "G37*",
                ]
            )
            runs += 1

    lines.extend(footer())
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return runs, w * h


def make_version(name: str, width: int | None) -> None:
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)

    img = Image.open(SRC)
    if width is not None and width != img.width:
        height = round(width * CARD_H / CARD_W)
        img = img.resize((width, height), Image.Resampling.LANCZOS).convert("L").point(lambda p: 255 if p >= 128 else 0)
    else:
        img = img.convert("L").point(lambda p: 255 if p >= 128 else 0)

    copper_pts = rounded_points(
        COPPER_INSET,
        COPPER_INSET,
        CARD_W - COPPER_INSET,
        CARD_H - COPPER_INSET,
        max(0, CORNER_R - COPPER_INSET),
        20,
    )
    write_region(folder / "photo_card.GTL", copper_pts)
    write_region(folder / "photo_card.GBL", copper_pts)
    runs, pixels = write_mask_from_bitmap(folder / "photo_card.GTS", img)
    write_outline(folder / "photo_card.GKO",)
    (folder / "photo_card.GBS").write_text("\n".join(header() + footer()) + "\n", encoding="ascii")
    (folder / "photo_card.GTO").write_text("\n".join(header() + footer()) + "\n", encoding="ascii")
    (folder / "photo_card.GBO").write_text("\n".join(header() + footer()) + "\n", encoding="ascii")

    readme = f"""Decorative ENIG photo PCB card

Size: {CARD_W:.2f} x {CARD_H:.2f} mm, rounded corners R{CORNER_R:.2f} mm
Source: {SRC.name}
Bitmap used: {img.width} x {img.height}
Approx dot size: {CARD_W / img.width:.4f} x {CARD_H / img.height:.4f} mm
Top soldermask opening runs: {runs}

Layer mapping:
- photo_card.GKO: board outline
- photo_card.GTL: solid top copper, inset {COPPER_INSET:.2f} mm
- photo_card.GTS: top soldermask openings from white pixels; these expose ENIG gold
- photo_card.GBL: solid bottom copper for balance
- photo_card.GBS: no bottom soldermask openings
- photo_card.GTO/photo_card.GBO: empty silkscreen layers

Recommended order settings:
- Surface finish: ENIG / immersion gold
- Soldermask color: black
- Silkscreen: none or black/white does not matter for this design
- Thickness: 0.8 mm or 1.0 mm for a card feel; 1.6 mm if you want a rigid board
- Confirm Gerber preview before ordering. Gold image should appear on the top soldermask layer openings.
"""
    (folder / "README.txt").write_text(readme, encoding="utf-8")

    zip_path = OUT / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in folder.iterdir():
            zf.write(file, file.name)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    make_version("safe_800", 800)
    make_version("fine_1600", None)


if __name__ == "__main__":
    main()

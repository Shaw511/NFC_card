from __future__ import annotations

import math
import zipfile
from pathlib import Path

from PIL import Image


SRC = Path("PCB_黑白双色_保细节抖动版.png")
BACK_SILK_SRC = Path("背面小图 签名.png")
OUT = Path("nfc_photo_pcb_gerber")
URL = "https://c6.y.qq.com/base/fcgi-bin/u?__=kIR6N1TP7wer"

BASE_CARD_W = 85.60
BASE_CARD_H = 52.54
SMT_MIN_SHORT_SIDE = 70.00
SCALE = SMT_MIN_SHORT_SIDE / BASE_CARD_H
CARD_W = BASE_CARD_W * SCALE
CARD_H = BASE_CARD_H * SCALE
CORNER_R = 3.18 * SCALE
PHOTO_W = 800
EDGE_CLEARANCE = 1.60 * SCALE
ANTENNA_WIDTH = 0.45
BACK_SILK_SIZE = 44.0 * SCALE


def sx(x: float) -> float:
    return x * SCALE


def sy(y: float) -> float:
    return y * SCALE


def gcoord(mm: float) -> str:
    return str(int(round(mm * 1_000_000)))


def xy(x: float, y: float) -> str:
    return f"X{gcoord(x)}Y{gcoord(y)}"


def header(extra_apertures: list[str] | None = None) -> list[str]:
    lines = [
        "G04 NFC decorative ENIG photo card prototype*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
        "%ADD10C,0.010*%",
    ]
    if extra_apertures:
        lines.extend(extra_apertures)
    lines.append("G54D10*")
    return lines


def footer() -> list[str]:
    return ["M02*"]


def rounded_points(x0: float, y0: float, x1: float, y1: float, r: float, steps: int = 18) -> list[tuple[float, float]]:
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


def write_outline(path: Path) -> None:
    lines = [
        f"G04 Board outline, {CARD_W:.2f} x {CARD_H:.2f} mm enlarged rounded card*",
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


def rect_region(lines: list[str], x0: float, y0: float, x1: float, y1: float) -> None:
    lines.extend(
        [
            "G36*",
            f"{xy(x0, y0)}D02*",
            f"{xy(x1, y0)}D01*",
            f"{xy(x1, y1)}D01*",
            f"{xy(x0, y1)}D01*",
            f"{xy(x0, y0)}D01*",
            "G37*",
        ]
    )


def circle_region(lines: list[str], cx: float, cy: float, r: float, steps: int = 24) -> None:
    pts = [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps)) for i in range(steps)]
    lines.append("G36*")
    lines.append(f"{xy(*pts[0])}D02*")
    for p in pts[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append(f"{xy(*pts[0])}D01*")
    lines.append("G37*")


def inside_card(x: float, y: float, margin: float) -> bool:
    x0, y0 = margin, margin
    x1, y1 = CARD_W - margin, CARD_H - margin
    r = max(0.0, CORNER_R - margin)
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    corners = [
        (x0 + r, y0 + r, x < x0 + r and y < y0 + r),
        (x1 - r, y0 + r, x > x1 - r and y < y0 + r),
        (x0 + r, y1 - r, x < x0 + r and y > y1 - r),
        (x1 - r, y1 - r, x > x1 - r and y > y1 - r),
    ]
    for cx, cy, active in corners:
        if active:
            return (x - cx) ** 2 + (y - cy) ** 2 <= r**2
    return True


def in_component_keepout(x: float, y: float) -> bool:
    return sx(63.0) <= x <= sx(84.0) and sy(39.0) <= y <= sy(51.5)


def add_photo_regions(lines: list[str], img: Image.Image, mask_only: bool = False) -> tuple[int, int]:
    bw = img.convert("L")
    w, h = bw.size
    px_w = CARD_W / w
    px_h = CARD_H / h
    pix = bw.load()
    runs = 0
    for row in range(h):
        y_top = CARD_H - row * px_h
        y_bot = CARD_H - (row + 1) * px_h
        y_mid = (y_top + y_bot) / 2
        col = 0
        while col < w:
            while col < w:
                x_mid = (col + 0.5) * px_w
                if (
                    pix[col, row] > 127
                    and inside_card(x_mid, y_mid, EDGE_CLEARANCE)
                    and not in_component_keepout(x_mid, y_mid)
                ):
                    break
                col += 1
            if col >= w:
                break
            start = col
            while col < w:
                x_mid = (col + 0.5) * px_w
                if (
                    pix[col, row] <= 127
                    or not inside_card(x_mid, y_mid, EDGE_CLEARANCE)
                    or in_component_keepout(x_mid, y_mid)
                ):
                    break
                col += 1
            x0 = start * px_w
            x1 = col * px_w
            rect_region(lines, x0, y_bot, x1, y_top)
            runs += 1
    return runs, w * h


def add_back_silkscreen(lines: list[str], img: Image.Image) -> tuple[int, int, float, float, float, float]:
    bw = img.convert("L").resize((520, 520), Image.Resampling.LANCZOS)
    bw = bw.point(lambda p: 255 if p < 150 else 0)
    bw = bw.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    w, h = bw.size
    scale = BACK_SILK_SIZE / max(w, h)
    draw_w = w * scale
    draw_h = h * scale
    x_origin = (CARD_W - draw_w) / 2
    y_origin = (CARD_H - draw_h) / 2
    pix = bw.load()
    runs = 0

    for row in range(h):
        y_top = y_origin + (h - row) * scale
        y_bot = y_origin + (h - row - 1) * scale
        y_mid = (y_top + y_bot) / 2
        col = 0
        while col < w:
            while col < w:
                x_mid = x_origin + (col + 0.5) * scale
                if pix[col, row] > 127 and inside_card(x_mid, y_mid, 1.4):
                    break
                col += 1
            if col >= w:
                break
            start = col
            while col < w:
                x_mid = x_origin + (col + 0.5) * scale
                if pix[col, row] <= 127 or not inside_card(x_mid, y_mid, 1.4):
                    break
                col += 1
            rect_region(lines, x_origin + start * scale, y_bot, x_origin + col * scale, y_top)
            runs += 1

    return runs, w * h, x_origin, y_origin, draw_w, draw_h


def draw_track(lines: list[str], points: list[tuple[float, float]], aperture: str = "D20") -> None:
    lines.append(f"G54{aperture}*")
    lines.append(f"{xy(*points[0])}D02*")
    for p in points[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append("G54D10*")


def add_pads(lines: list[str], include_testpads: bool = True) -> None:
    # U1: NT3H2111W0FTT, TSSOP-8, top side.
    left_x, right_x = sx(70.6), sx(75.8)
    ys_left = [sy(v) for v in [45.975, 45.325, 44.675, 44.025]]
    ys_right = [sy(v) for v in [44.025, 44.675, 45.325, 45.975]]
    for y in ys_left:
        rect_region(lines, left_x - 0.28, y - 0.60, left_x + 0.28, y + 0.60)
    for y in ys_right:
        rect_region(lines, right_x - 0.28, y - 0.60, right_x + 0.28, y + 0.60)

    # R1 0603, D1 0603, C1 0603.
    for cx, cy in [(sx(x), sy(y)) for x, y in [(78.0, 45.3), (79.6, 45.3), (81.1, 45.3), (82.7, 45.3), (78.0, 43.3), (79.6, 43.3)]]:
        rect_region(lines, cx - 0.45, cy - 0.40, cx + 0.45, cy + 0.40)

    if include_testpads:
        for cx, cy in [(sx(x), sy(y)) for x, y in [(64.0, 41.0), (66.0, 41.0), (68.0, 41.0), (70.0, 41.0), (72.0, 41.0)]]:
            circle_region(lines, cx, cy, 0.55)


def add_circuit_tracks(lines: list[str]) -> None:
    antenna_base = [
        (75.8, 45.975),
        (83.0, 45.975),
        (83.0, 2.5),
        (2.5, 2.5),
        (2.5, 50.0),
        (83.1, 50.0),
        (83.1, 3.3),
        (3.3, 3.3),
        (3.3, 49.2),
        (82.3, 49.2),
        (82.3, 4.1),
        (4.1, 4.1),
        (4.1, 48.4),
        (81.5, 48.4),
        (81.5, 4.9),
        (4.9, 4.9),
        (4.9, 47.6),
        (70.6, 47.6),
        (70.6, 45.975),
    ]
    antenna = [(sx(x), sy(y)) for x, y in antenna_base]
    draw_track(lines, antenna)

    # VOUT/VCC to resistor, LED, and storage capacitor. LED anode faces VOUT.
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(75.8, 45.325), (76.6, 45.325), (76.6, 45.3), (77.55, 45.3)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(75.8, 44.675), (76.6, 44.675), (76.6, 45.325)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(78.45, 45.3), (79.15, 45.3)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(80.05, 45.3), (80.65, 45.3)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(77.55, 43.3), (76.6, 43.3), (76.6, 45.325)]], "D21")

    # Ground net: U1 VSS to LED cathode, C1, and GND test pad.
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(70.6, 45.325), (68.8, 45.325), (68.8, 43.3), (79.15, 43.3)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(81.55, 45.3), (81.55, 43.3), (80.05, 43.3)]], "D21")

    # Test pads: SCL, FD, SDA, VOUT, GND.
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(70.6, 44.675), (64.0, 41.0)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(70.6, 44.025), (66.0, 41.0)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(75.8, 44.025), (68.0, 41.0)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(76.6, 45.325), (70.0, 41.0)]], "D21")
    draw_track(lines, [(sx(x), sy(y)) for x, y in [(68.8, 43.3), (72.0, 41.0)]], "D21")


def make_ndef_notes() -> str:
    uri_id = 0x04  # https://
    rest = URL.removeprefix("https://")
    payload = bytes([uri_id]) + rest.encode("ascii")
    record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    pages = [tlv[i : i + 4] for i in range(0, len(tlv), 4)]
    page_lines = []
    for idx, page in enumerate(pages, start=4):
        padded = page.ljust(4, b"\x00")
        page_lines.append(f"Page {idx:02d}: " + " ".join(f"{b:02X}" for b in padded))
    return "\n".join(page_lines)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    folder = OUT / "nfc_photo_card_proto_v1"
    folder.mkdir(parents=True, exist_ok=True)

    img = Image.open(SRC)
    img = img.resize((PHOTO_W, round(PHOTO_W * CARD_H / CARD_W)), Image.Resampling.LANCZOS)
    img = img.convert("L").point(lambda p: 255 if p >= 128 else 0)

    copper = header(["%ADD20C,0.450*%", "%ADD21C,0.250*%"])
    add_photo_regions(copper, img)
    add_circuit_tracks(copper)
    add_pads(copper)
    copper.extend(footer())
    (folder / "nfc_photo_card.GTL").write_text("\n".join(copper) + "\n", encoding="ascii")

    mask = header()
    runs, _ = add_photo_regions(mask, img, mask_only=True)
    add_pads(mask)
    mask.extend(footer())
    (folder / "nfc_photo_card.GTS").write_text("\n".join(mask) + "\n", encoding="ascii")

    paste = header()
    add_pads(paste, include_testpads=False)
    paste.extend(footer())
    (folder / "nfc_photo_card.GTP").write_text("\n".join(paste) + "\n", encoding="ascii")

    write_outline(folder / "nfc_photo_card.GKO")
    for empty in ["GBL", "GBS", "GTO", "GBP"]:
        (folder / f"nfc_photo_card.{empty}").write_text("\n".join(header() + footer()) + "\n", encoding="ascii")

    back_silk_runs = 0
    back_silk_box = (0.0, 0.0, 0.0, 0.0)
    if BACK_SILK_SRC.exists():
        back_img = Image.open(BACK_SILK_SRC)
        back_silk = header()
        back_silk_runs, _, bx, by, bw, bh = add_back_silkscreen(back_silk, back_img)
        back_silk_box = (bx, by, bw, bh)
        back_silk.extend(footer())
        (folder / "nfc_photo_card.GBO").write_text("\n".join(back_silk) + "\n", encoding="ascii")
    else:
        (folder / "nfc_photo_card.GBO").write_text("\n".join(header() + footer()) + "\n", encoding="ascii")

    bom = f"""Design: NFC ENIG photo card prototype v1

U1: NT3H2111W0FTTJ, NXP NTAG I2C plus 1K, TSSOP-8
R1: 330 ohm, 0603, LED current limit
D1: 0603 low-current yellow/amber LED, Vf <= 2.0 V preferred
C1: 220 nF, 0603, X7R, VOUT energy-harvesting reservoir
Optional: keep 0 ohm / 4.7 pF / 10 pF 0603 parts available for antenna tuning rework if read range is poor.

Order settings:
- 2-layer PCB
- Black soldermask
- ENIG / immersion gold
- 1.6 mm board thickness recommended for SMT ordering
- 1 oz copper

Notes:
- This is a prototype antenna. Phone read range depends strongly on copper artwork, phone model, board thickness, and assembled component parasitics.
- The LED uses harvested NFC energy, so it lights only when the phone is close and may reduce NFC read range.
- Program the URL as an NDEF URI after assembly unless your assembler can pre-program U1.
- U1 pin map used here: 1 LA, 2 VSS, 3 SCL, 4 FD, 5 SDA, 6 VCC, 7 VOUT, 8 LB.
- Back silkscreen image: {BACK_SILK_SRC.name if BACK_SILK_SRC.exists() else "not found"}, centered about {back_silk_box[2]:.1f} x {back_silk_box[3]:.1f} mm.
"""
    (folder / "BOM_and_order_notes.txt").write_text(bom, encoding="utf-8")

    ndef = f"""URL:
{URL}

NDEF URI TLV bytes for NTAG memory, starting at user memory page 04.
URI prefix code 04 means https://

{make_ndef_notes()}
"""
    (folder / "NDEF_URL_programming.txt").write_text(ndef, encoding="utf-8")

    readme = f"""NFC photo PCB card prototype v1

Function:
- Tap with a phone: NT3H2111 NFC tag opens this URL: {URL}
- During RF field presence: VOUT harvests energy and lights a low-current LED.
- Front visual: gold photo pixels on black soldermask, with antenna mostly hidden under soldermask.
- Board size: {CARD_W:.2f} x {CARD_H:.2f} mm, scaled {SCALE:.4f}x from 85.60 x 52.54 mm so the short side reaches 70.00 mm.

Layer mapping:
- nfc_photo_card.GKO: board outline
- nfc_photo_card.GTL: top copper photo pixels, NFC antenna, pads, and traces
- nfc_photo_card.GTS: top soldermask openings for photo gold pixels and component pads
- nfc_photo_card.GTP: top paste for SMT assembly
- nfc_photo_card.GBO: bottom silkscreen signature image from {BACK_SILK_SRC.name if BACK_SILK_SRC.exists() else "missing source"}
- Bottom copper and bottom soldermask openings are intentionally empty.

Important:
- This is a manufacturable prototype, not a guaranteed tuned RF production antenna.
- After the first board, verify read range and LED behavior. If read range is poor, tune antenna capacitance or reduce LED load.
- Photo bitmap used: {img.width} x {img.height}, mask opening runs: {runs}
- Back silkscreen size: {back_silk_box[2]:.1f} x {back_silk_box[3]:.1f} mm, silk opening runs: {back_silk_runs}
"""
    (folder / "README.txt").write_text(readme, encoding="utf-8")

    zip_path = OUT / "nfc_photo_card_proto_v1.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in folder.iterdir():
            zf.write(file, file.name)


if __name__ == "__main__":
    main()

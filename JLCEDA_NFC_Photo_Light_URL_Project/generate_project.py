from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
BUILD = OUT / "build"
GERBER = OUT / "gerber"

FRONT_PHOTO = ROOT / "PCB_黑白双色_保细节抖动版.png"
BACK_SIGNATURE = ROOT / "背面小图 签名.png"
URL = "https://c6.y.qq.com/base/fcgi-bin/u?__=kIR6N1TP7wer"

# Enlarged from a credit-card outline so JLC SMT assembly has a 70 mm short side.
BASE_W = 85.60
BASE_H = 52.54
SCALE = 70.00 / BASE_H
CARD_W = BASE_W * SCALE
CARD_H = 70.00
CORNER_R = 3.18 * SCALE

PHOTO_PX_W = 900
EDGE_CLEAR = 1.6
# Map the source photo slightly larger than the first version while preserving
# a narrow soldermask border and NFC antenna keepout.
PHOTO_DRAW_W = 102.0
PHOTO_DRAW_H = PHOTO_DRAW_W * BASE_H / BASE_W
PHOTO_BOX = (
    (CARD_W - PHOTO_DRAW_W) / 2,
    (CARD_H - PHOTO_DRAW_H) / 2,
    (CARD_W + PHOTO_DRAW_W) / 2,
    (CARD_H + PHOTO_DRAW_H) / 2,
)
ANT_KEEP = 6.5
TOP_RIGHT_KEEP = (82.0, 49.0, CARD_W - 2.0, CARD_H - 2.0)
BACK_SIZE = 44.0 * SCALE

OX = 4000.0
OY = 3000.0
EASYEDA_UNIT_MM = 0.254
POWER_VIAS = [(100.2, 63.0), (108.8, 63.0)]
ANT_VIAS = [(88.0, 50.4), (96.4, 63.0)]
U1_LEFT_X = 91.5
U1_RIGHT_X = 96.1
U1_Y = [60.825, 60.175, 59.525, 58.875]


class Ids:
    def __init__(self) -> None:
        self.value = 1

    def next(self) -> str:
        gid = f"gge{self.value}"
        self.value += 1
        return gid


ids = Ids()


def f(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".")


def ex(x: float) -> float:
    return OX + x / EASYEDA_UNIT_MM


def ey(y: float) -> float:
    return OY + (CARD_H - y) / EASYEDA_UNIT_MM


def eu(v: float) -> float:
    return v / EASYEDA_UNIT_MM


def gcoord(mm: float) -> str:
    return str(int(round(mm * 1_000_000)))


def xy(x: float, y: float) -> str:
    return f"X{gcoord(x)}Y{gcoord(y)}"


def rounded_points(x0: float, y0: float, x1: float, y1: float, r: float, steps: int = 20) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    corners = [
        (x1 - r, y1 - r, 0, 90),
        (x0 + r, y1 - r, 90, 180),
        (x0 + r, y0 + r, 180, 270),
        (x1 - r, y0 + r, 270, 360),
    ]
    for cx, cy, a0, a1 in corners:
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def inside_card(x: float, y: float, margin: float) -> bool:
    x0, y0 = margin, margin
    x1, y1 = CARD_W - margin, CARD_H - margin
    r = max(0.0, CORNER_R - margin)
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    corner_tests = [
        (x0 + r, y0 + r, x < x0 + r and y < y0 + r),
        (x1 - r, y0 + r, x > x1 - r and y < y0 + r),
        (x0 + r, y1 - r, x < x0 + r and y > y1 - r),
        (x1 - r, y1 - r, x > x1 - r and y > y1 - r),
    ]
    for cx, cy, active in corner_tests:
        if active:
            return (x - cx) ** 2 + (y - cy) ** 2 <= r**2
    return True


def in_box(x: float, y: float, box: tuple[float, float, float, float]) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def in_antenna_keepout(x: float, y: float) -> bool:
    # Keep the photo copper away from the independent NFC loop corridor.
    return x < ANT_KEEP or y < ANT_KEEP or y > CARD_H - ANT_KEEP or x > CARD_W - ANT_KEEP


def dist_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def near_polyline(x: float, y: float, points: list[tuple[float, float]], radius: float) -> bool:
    return any(dist_to_segment(x, y, ax, ay, bx, by) <= radius for (ax, ay), (bx, by) in zip(points, points[1:]))


def in_electrical_keepout(x: float, y: float) -> bool:
    # Only front-side LED hardware can short to the decorative photo copper.
    for px, py in [(100.7, 64.7), (102.3, 64.7), (105.5, 64.7), (107.1, 64.7), (100.2, 63.0), (108.8, 63.0)]:
        if abs(x - px) <= 1.1 and abs(y - py) <= 1.0:
            return True

    return False


def in_photo_allowed(x: float, y: float) -> bool:
    return (
        in_box(x, y, PHOTO_BOX)
        and inside_card(x, y, EDGE_CLEAR)
        and not in_antenna_keepout(x, y)
        and not in_box(x, y, TOP_RIGHT_KEEP)
        and not in_electrical_keepout(x, y)
    )


def gerber_header(extra: list[str] | None = None) -> list[str]:
    lines = [
        "G04 JLCEDA NFC photo light URL card*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
        "%ADD10C,0.010*%",
    ]
    if extra:
        lines.extend(extra)
    lines.append("G54D10*")
    return lines


def gerber_footer() -> list[str]:
    return ["M02*"]


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


def circle_region(lines: list[str], cx: float, cy: float, r: float, steps: int = 32) -> None:
    pts = [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps)) for i in range(steps)]
    lines.append("G36*")
    lines.append(f"{xy(*pts[0])}D02*")
    for p in pts[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append(f"{xy(*pts[0])}D01*")
    lines.append("G37*")


def add_image_runs(lines: list[str], img: Image.Image, box: tuple[float, float, float, float], allowed) -> int:
    bw = img.convert("L")
    px_w = (box[2] - box[0]) / bw.width
    px_h = (box[3] - box[1]) / bw.height
    pix = bw.load()
    runs = 0
    for row in range(bw.height):
        y_top = box[3] - row * px_h
        y_bot = box[3] - (row + 1) * px_h
        y_mid = (y_top + y_bot) / 2
        col = 0
        while col < bw.width:
            while col < bw.width:
                x_mid = box[0] + (col + 0.5) * px_w
                if pix[col, row] > 127 and allowed(x_mid, y_mid):
                    break
                col += 1
            if col >= bw.width:
                break
            start = col
            while col < bw.width:
                x_mid = box[0] + (col + 0.5) * px_w
                if pix[col, row] <= 127 or not allowed(x_mid, y_mid):
                    break
                col += 1
            rect_region(lines, box[0] + start * px_w, y_bot, box[0] + col * px_w, y_top)
            runs += 1
    return runs


def draw_track(lines: list[str], points: list[tuple[float, float]], aperture: str = "D20") -> None:
    lines.append(f"G54{aperture}*")
    lines.append(f"{xy(*points[0])}D02*")
    for p in points[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append("G54D10*")


def antenna_points() -> list[tuple[float, float]]:
    return [
        (88.0, 61.8),
        (81.5, 61.8),
        (81.5, 10.0),
        (10.0, 10.0),
        (10.0, 60.0),
        (80.0, 60.0),
        (80.0, 11.6),
        (11.6, 11.6),
        (11.6, 58.4),
        (78.4, 58.4),
        (78.4, 13.2),
        (13.2, 13.2),
        (13.2, 56.8),
        (76.8, 56.8),
        (76.8, 14.8),
        (14.8, 14.8),
        (14.8, 55.2),
        (75.2, 55.2),
        (75.2, 16.4),
        (16.4, 16.4),
        (16.4, 53.6),
        (73.6, 53.6),
        (73.6, 18.0),
        (18.0, 18.0),
        (18.0, 52.0),
        (72.0, 52.0),
        (72.0, 19.6),
        (19.6, 19.6),
        (19.6, 50.4),
        (88.0, 50.4),
    ]


def bottom_circuit_tracks() -> list[tuple[list[tuple[float, float]], str]]:
    return [
        (antenna_points(), "D20"),
        ([(88.0, 61.8), (U1_LEFT_X, U1_Y[0])], "D21"),
        ([(U1_RIGHT_X, U1_Y[0]), (96.4, 63.0)], "D21"),
        ([(U1_RIGHT_X, U1_Y[1]), (100.2, U1_Y[1]), (100.2, 63.0)], "D21"),
        ([(U1_RIGHT_X, U1_Y[2]), (U1_RIGHT_X, U1_Y[1])], "D21"),
        ([(100.2, U1_Y[1]), (100.2, 56.0), (102.0, 56.0)], "D21"),
        ([(U1_LEFT_X, U1_Y[1]), (94.0, U1_Y[1]), (108.8, U1_Y[1]), (108.8, 63.0)], "D21"),
        ([(104.9, 56.0), (108.8, 56.0), (108.8, 60.5)], "D21"),
        ([(U1_LEFT_X, U1_Y[2]), (86.0, 52.0)], "D21"),
        ([(U1_LEFT_X, U1_Y[3]), (88.5, 52.0)], "D21"),
        ([(U1_RIGHT_X, U1_Y[3]), (91.0, 52.0)], "D21"),
        ([(100.2, U1_Y[1]), (93.5, 52.0)], "D21"),
        ([(108.8, U1_Y[1]), (96.0, 52.0)], "D21"),
    ]


def top_antenna_jumper_tracks() -> list[tuple[list[tuple[float, float]], str]]:
    return [
        ([(88.0, 50.4), (96.4, 63.0)], "D21"),
    ]


def front_led_tracks() -> list[tuple[list[tuple[float, float]], str]]:
    return [
        ([(100.2, 63.0), (100.2, 64.7), (100.1, 64.7)], "D21"),
        ([(103.0, 64.7), (104.9, 64.7)], "D21"),
        ([(107.8, 64.7), (108.8, 64.7), (108.8, 63.0)], "D21"),
    ]


def add_bottom_pads(lines: list[str], testpads: bool = True, vias: bool = True) -> None:
    for x, y in [(U1_LEFT_X, U1_Y[0]), (U1_LEFT_X, U1_Y[1]), (U1_LEFT_X, U1_Y[2]), (U1_LEFT_X, U1_Y[3]), (U1_RIGHT_X, U1_Y[3]), (U1_RIGHT_X, U1_Y[2]), (U1_RIGHT_X, U1_Y[1]), (U1_RIGHT_X, U1_Y[0])]:
        rect_region(lines, x - 0.55, y - 0.18, x + 0.55, y + 0.18)
    for x, y in [(102.6, 56.0), (104.2, 56.0)]:
        rect_region(lines, x - 0.45, y - 0.40, x + 0.45, y + 0.40)
    if testpads:
        for x, y in [(86.0, 52.0), (88.5, 52.0), (91.0, 52.0), (93.5, 52.0), (96.0, 52.0)]:
            circle_region(lines, x, y, 0.55)
    if vias:
        for x, y in POWER_VIAS + ANT_VIAS:
            circle_region(lines, x, y, 0.45)


def add_front_led_pads(lines: list[str], vias: bool = True) -> None:
    for x, y in [(100.7, 64.7), (102.3, 64.7), (105.5, 64.7), (107.1, 64.7)]:
        rect_region(lines, x - 0.45, y - 0.40, x + 0.45, y + 0.40)
    if vias:
        for x, y in POWER_VIAS + ANT_VIAS:
            circle_region(lines, x, y, 0.45)


def write_drill(path: Path) -> None:
    lines = [
        "M48",
        "METRIC,TZ",
        "T01C0.300",
        "%",
        "T01",
        *[xy(x, y) for x, y in POWER_VIAS + ANT_VIAS],
        "M30",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def write_outline(path: Path) -> None:
    lines = [
        "G04 Board outline*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
        "%ADD10C,0.100*%",
        "G54D10*",
    ]
    pts = rounded_points(0, 0, CARD_W, CARD_H, CORNER_R)
    lines.append(f"{xy(*pts[0])}D02*")
    for p in pts[1:]:
        lines.append(f"{xy(*p)}D01*")
    lines.append(f"{xy(*pts[0])}D01*")
    lines.extend(gerber_footer())
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def easy_path_rect(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"M {f(ex(x0))} {f(ey(y0))} L {f(ex(x1))} {f(ey(y0))} L {f(ex(x1))} {f(ey(y1))} L {f(ex(x0))} {f(ey(y1))} Z"


def solid(layer: int, path: str) -> str:
    return f"SOLIDREGION~{layer}~~{path}~solid~{ids.next()}~~~~0"


def easy_track(layer: int, width: float, points: list[tuple[float, float]]) -> str:
    pts = " ".join(f"{f(ex(x))} {f(ey(y))}" for x, y in points)
    return f"TRACK~{f(eu(width))}~{layer}~~{pts}~{ids.next()}~0"


def easy_pad_rect(x: float, y: float, w: float, h: float, number: str, layer: int = 1) -> str:
    pts = f"{f(ex(x-w/2))} {f(ey(y-h/2))} {f(ex(x+w/2))} {f(ey(y-h/2))} {f(ex(x+w/2))} {f(ey(y+h/2))} {f(ex(x-w/2))} {f(ey(y+h/2))}"
    return f"PAD~RECT~{f(ex(x))}~{f(ey(y))}~{f(eu(w))}~{f(eu(h))}~{layer}~~{number}~0~{pts}~0~{ids.next()}~0~~Y~0~0~0.4~{f(ex(x))},{f(ey(y))}"


def easy_pad_circle(x: float, y: float, d: float, number: str, layer: int = 1) -> str:
    return f"PAD~ELLIPSE~{f(ex(x))}~{f(ey(y))}~{f(eu(d))}~{f(eu(d))}~{layer}~~{number}~0~~0~{ids.next()}~0~~Y~0~0~0.4~{f(ex(x))},{f(ey(y))}"


def make_ndef_notes() -> str:
    rest = URL.removeprefix("https://")
    payload = bytes([0x04]) + rest.encode("ascii")
    record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    pages = []
    for i in range(0, len(tlv), 4):
        page = tlv[i : i + 4].ljust(4, b"\x00")
        pages.append(f"Page {4 + i // 4:02d}: " + " ".join(f"{b:02X}" for b in page))
    return "\n".join(pages)


def prepare_front_image() -> Image.Image:
    img = Image.open(FRONT_PHOTO).convert("L")
    h = round(PHOTO_PX_W * (PHOTO_BOX[3] - PHOTO_BOX[1]) / (PHOTO_BOX[2] - PHOTO_BOX[0]))
    return img.resize((PHOTO_PX_W, h), Image.Resampling.LANCZOS).point(lambda p: 255 if p >= 128 else 0)


def prepare_back_image() -> tuple[Image.Image, tuple[float, float, float, float]]:
    img = Image.open(BACK_SIGNATURE).convert("L").resize((520, 520), Image.Resampling.LANCZOS)
    img = img.point(lambda p: 255 if p < 150 else 0).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    scale = BACK_SIZE / max(img.size)
    w, h = img.width * scale, img.height * scale
    return img, ((CARD_W - w) / 2, (CARD_H - h) / 2, (CARD_W + w) / 2, (CARD_H + h) / 2)


def build() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    GERBER.mkdir(parents=True, exist_ok=True)

    front = prepare_front_image()
    back, back_box = prepare_back_image()

    top = gerber_header(["%ADD20C,0.450*%", "%ADD21C,0.250*%"])
    photo_runs = add_image_runs(top, front, PHOTO_BOX, in_photo_allowed)
    for pts, aperture in top_antenna_jumper_tracks():
        draw_track(top, pts, aperture)
    for pts, aperture in front_led_tracks():
        draw_track(top, pts, aperture)
    add_front_led_pads(top)
    top.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GTL").write_text("\n".join(top) + "\n", encoding="ascii")

    mask = gerber_header()
    add_image_runs(mask, front, PHOTO_BOX, in_photo_allowed)
    add_front_led_pads(mask)
    mask.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GTS").write_text("\n".join(mask) + "\n", encoding="ascii")

    paste = gerber_header()
    add_front_led_pads(paste, vias=False)
    paste.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GTP").write_text("\n".join(paste) + "\n", encoding="ascii")

    bottom = gerber_header(["%ADD20C,0.450*%", "%ADD21C,0.250*%"])
    for pts, aperture in bottom_circuit_tracks():
        draw_track(bottom, pts, aperture)
    add_bottom_pads(bottom)
    bottom.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GBL").write_text("\n".join(bottom) + "\n", encoding="ascii")

    bottom_mask = gerber_header()
    add_bottom_pads(bottom_mask)
    bottom_mask.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GBS").write_text("\n".join(bottom_mask) + "\n", encoding="ascii")

    bottom_paste = gerber_header()
    add_bottom_pads(bottom_paste, testpads=False, vias=False)
    bottom_paste.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GBP").write_text("\n".join(bottom_paste) + "\n", encoding="ascii")

    back_silk = gerber_header()
    back_runs = add_image_runs(back_silk, back, back_box, lambda x, y: inside_card(x, y, 1.4))
    back_silk.extend(gerber_footer())
    (GERBER / "nfc_photo_light_url.GBO").write_text("\n".join(back_silk) + "\n", encoding="ascii")

    write_outline(GERBER / "nfc_photo_light_url.GKO")
    write_drill(GERBER / "nfc_photo_light_url.TXT")
    for suffix in ["GTO"]:
        (GERBER / f"nfc_photo_light_url.{suffix}").write_text("\n".join(gerber_header() + gerber_footer()) + "\n", encoding="ascii")

    easy_shapes: list[str] = []
    outline = rounded_points(0, 0, CARD_W, CARD_H, CORNER_R)
    easy_shapes.append(easy_track(10, 0.1, outline + [outline[0]]))

    def easy_runs(img: Image.Image, box: tuple[float, float, float, float], layer: int, allowed) -> int:
        bw = img.convert("L")
        px_w = (box[2] - box[0]) / bw.width
        px_h = (box[3] - box[1]) / bw.height
        pix = bw.load()
        runs = 0
        for row in range(bw.height):
            y_top = box[3] - row * px_h
            y_bot = box[3] - (row + 1) * px_h
            y_mid = (y_top + y_bot) / 2
            col = 0
            while col < bw.width:
                while col < bw.width:
                    x_mid = box[0] + (col + 0.5) * px_w
                    if pix[col, row] > 127 and allowed(x_mid, y_mid):
                        break
                    col += 1
                if col >= bw.width:
                    break
                start = col
                while col < bw.width:
                    x_mid = box[0] + (col + 0.5) * px_w
                    if pix[col, row] <= 127 or not allowed(x_mid, y_mid):
                        break
                    col += 1
                easy_shapes.append(solid(layer, easy_path_rect(box[0] + start * px_w, y_bot, box[0] + col * px_w, y_top)))
                runs += 1
        return runs

    easy_runs(front, PHOTO_BOX, 1, in_photo_allowed)
    easy_runs(front, PHOTO_BOX, 7, in_photo_allowed)
    for pts, aperture in top_antenna_jumper_tracks():
        easy_shapes.append(easy_track(1, 0.45 if aperture == "D20" else 0.25, pts))
    for pts, aperture in front_led_tracks():
        easy_shapes.append(easy_track(1, 0.45 if aperture == "D20" else 0.25, pts))
    for pts, aperture in bottom_circuit_tracks():
        easy_shapes.append(easy_track(2, 0.45 if aperture == "D20" else 0.25, pts))
    for number, x, y in [
        ("1", U1_LEFT_X, U1_Y[0]),
        ("2", U1_LEFT_X, U1_Y[1]),
        ("3", U1_LEFT_X, U1_Y[2]),
        ("4", U1_LEFT_X, U1_Y[3]),
        ("5", U1_RIGHT_X, U1_Y[3]),
        ("6", U1_RIGHT_X, U1_Y[2]),
        ("7", U1_RIGHT_X, U1_Y[1]),
        ("8", U1_RIGHT_X, U1_Y[0]),
    ]:
        easy_shapes.append(easy_pad_rect(x, y, 1.10, 0.36, number, layer=2))
    for number, x, y in [("C1-1", 102.6, 56.0), ("C1-2", 104.2, 56.0)]:
        easy_shapes.append(easy_pad_rect(x, y, 0.90, 0.80, number, layer=2))
    for number, x, y in [("R1-1", 100.7, 64.7), ("R1-2", 102.3, 64.7), ("D1-A", 105.5, 64.7), ("D1-K", 107.1, 64.7)]:
        easy_shapes.append(easy_pad_rect(x, y, 0.90, 0.80, number))
    for number, x, y in [("TP-SCL", 86.0, 52.0), ("TP-FD", 88.5, 52.0), ("TP-SDA", 91.0, 52.0), ("TP-VOUT", 93.5, 52.0), ("TP-GND", 96.0, 52.0)]:
        easy_shapes.append(easy_pad_circle(x, y, 1.10, number, layer=2))
    for number, x, y in [("VIA-VOUT", 100.2, 63.0), ("VIA-GND", 108.8, 63.0), ("VIA-ANT-LB", 88.0, 50.4), ("VIA-ANT-U1", 96.4, 63.0)]:
        easy_shapes.append(easy_pad_circle(x, y, 0.90, number, layer=11))
    easy_runs(back, back_box, 4, lambda x, y: inside_card(x, y, 1.4))

    pcb = {
        "head": {"docType": "3", "editorVersion": "6.5.22", "newgId": True, "c_para": {}, "hasIdFlag": True},
        "canvas": f"CA~1000~1000~#000000~yes~#FFFFFF~10~1000~1000~line~0.5~mm~0.25~45~~0.5~{f(ex(CARD_W / 2))}~{f(ey(CARD_H / 2))}~0~yes",
        "shape": easy_shapes,
        "layers": [
            "1~TopLayer~#FF0000~true~true~true~",
            "2~BottomLayer~#0000FF~true~false~true~",
            "3~TopSilkLayer~#FFCC00~true~false~true~",
            "4~BottomSilkLayer~#66CC33~true~false~true~",
            "5~TopPasteMaskLayer~#808080~true~false~true~",
            "6~BottomPasteMaskLayer~#800000~true~false~true~",
            "7~TopSolderMaskLayer~#800080~true~false~true~0.3",
            "8~BottomSolderMaskLayer~#AA00FF~true~false~true~0.3",
            "10~BoardOutLine~#FF00FF~true~false~true~",
            "11~Multi-Layer~#C0C0C0~true~false~true~",
            "12~Document~#FFFFFF~true~false~true~",
        ],
        "objects": ["All~true~false", "Component~true~true", "Track~true~true", "Pad~true~true", "Solid_Region~true~true", "Text~true~true", "Image~true~true"],
        "BBox": {"x": OX, "y": OY, "width": eu(CARD_W), "height": eu(CARD_H)},
        "DRCRULE": {"Default": {"trackWidth": 0.25, "clearance": 0.15, "viaHoleDiameter": 0.6, "viaHoleD": 0.3}, "isRealtime": False},
    }

    json_path = OUT / "NFC_Photo_Light_URL_EasyEDA_Std_PCB.json"
    json_path.write_text(json.dumps(pcb, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    (OUT / "BOM.csv").write_text(
        "Comment,Designator,Footprint,LCSC Part #\n"
        "NT3H2111W0FTTJ,U1,TSSOP-8_L4.4-W3.0-P0.65-LS6.4-BR,C2654884\n"
        "330R,R1,R0603,C23138\n"
        "LED_YELLOW_0603,D1,0603,C264455\n"
        "220nF_X7R,C1,C0603,C519574\n",
        encoding="utf-8-sig",
    )
    (OUT / "CPL.csv").write_text(
        "Designator,Mid X,Mid Y,Layer,Rotation\n"
        "U1,93.8,59.85,Bottom,0\n"
        "R1,101.5,64.7,Top,0\n"
        "D1,106.3,64.7,Top,0\n"
        "C1,103.4,56.0,Bottom,0\n",
        encoding="utf-8-sig",
    )
    (OUT / "NDEF_URL_programming.txt").write_text(
        f"URL:\n{URL}\n\nNDEF URI TLV bytes, write from NTAG user memory page 04.\nURI prefix 04 means https://\n\n{make_ndef_notes()}\n",
        encoding="utf-8-sig",
    )
    (OUT / "README_导入与下单说明.md").write_text(
        f"""# 嘉立创 EDA NFC 沉金照片亮灯卡

## 文件

- `NFC_Photo_Light_URL_EasyEDA_Std_Project.zip`：嘉立创 EDA 标准版 PCB 工程压缩包，优先导入这个。
- `NFC_Photo_Light_URL_EasyEDA_Std_PCB.json`：如果 ZIP 导入失败，导入这个单 PCB JSON。
- `NFC_Photo_Light_URL_Gerber.zip`：Gerber 生产文件。
- `BOM.csv` / `CPL.csv`：SMT 贴片参考文件。
- `NDEF_URL_programming.txt`：把网址写进 NFC 芯片的字节。

## 设计约束

- 正面照片使用 `{FRONT_PHOTO.name}`：白色像素在 TopLayer 铺铜并在 TopSolderMaskLayer 开窗，黑色像素不开窗；下单选择黑色阻焊 + 沉金后，白色区域露出沉金。
- NFC 天线、U1 芯片、C1 储能电容和 5 个测试点移到底层/背面，避免正面天线框遮挡人像。
- 正面右上角只保留 R1 限流电阻和 D1 LED，通过两个 0.3 mm 金属化过孔连接到底层 VOUT/GND。
- 背面签名使用 `{BACK_SIGNATURE.name}`，放在 BottomSilkLayer，已做背面镜像处理。
- D1 通过 U1 的 VOUT 能量采集输出点亮；手机靠近时读取 U1 内的 NDEF URL。

## 下单建议

- 2 层板，黑色阻焊，沉金 / ENIG，1 oz 铜。
- 0.8 mm 或 1.0 mm 更像卡片；需要贴片稳定性可选 1.6 mm。
- 这是未实测调谐的第一版 NFC 原型。正面照片铜皮仍会影响底层天线读距，首批建议小批量打样后按读距调整天线或减少照片铜面积。
- 如果嘉立创贴片不支持本单的双面贴装组合，可选择只贴正面 LED/R1，背面 U1/C1 手焊，或反过来按装配能力调整元件面。

## 写入网址

目标 URL：`{URL}`

贴片后可用 NFC Tools、NXP TagWriter 或量产烧录服务写入 `NDEF_URL_programming.txt` 中的内容。

生成信息：板尺寸 {CARD_W:.2f} mm x {CARD_H:.2f} mm；正面照片开窗 run 数 {photo_runs}；背面丝印 run 数 {back_runs}。
""",
        encoding="utf-8-sig",
    )

    gerber_zip = OUT / "NFC_Photo_Light_URL_Gerber.zip"
    if gerber_zip.exists():
        gerber_zip.unlink()
    with zipfile.ZipFile(gerber_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in GERBER.iterdir():
            zf.write(file, file.name)

    project_zip = OUT / "NFC_Photo_Light_URL_EasyEDA_Std_Project.zip"
    if project_zip.exists():
        project_zip.unlink()
    with zipfile.ZipFile(project_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(json_path, json_path.name)
        for name in ["README_导入与下单说明.md", "BOM.csv", "CPL.csv", "NDEF_URL_programming.txt"]:
            zf.write(OUT / name, name)


if __name__ == "__main__":
    build()

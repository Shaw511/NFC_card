from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PIL import Image

import make_nfc_photo_pcb_gerbers as src


OUT = Path("easyeda_std_project")
JSON_PATH = OUT / "NFC_Photo_Card_EasyEDA_Std_PCB.json"
ZIP_PATH = OUT / "NFC_Photo_Card_EasyEDA_Std_Project.zip"

OX = 4000.0
OY = 3000.0


class Ids:
    def __init__(self) -> None:
        self.n = 1

    def next(self) -> str:
        value = f"gge{self.n}"
        self.n += 1
        return value


ids = Ids()


def fx(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


def ex(x: float) -> float:
    return OX + x


def ey(y: float) -> float:
    return OY + (src.CARD_H - y)


def path_rect(x0: float, y0: float, x1: float, y1: float) -> str:
    return (
        f"M {fx(ex(x0))} {fx(ey(y0))} "
        f"L {fx(ex(x1))} {fx(ey(y0))} "
        f"L {fx(ex(x1))} {fx(ey(y1))} "
        f"L {fx(ex(x0))} {fx(ey(y1))} Z"
    )


def solid(layer: int, path: str, net: str = "") -> str:
    return f"SOLIDREGION~{layer}~{net}~{path}~solid~{ids.next()}~~~~0"


def track(layer: int, width: float, points: list[tuple[float, float]], net: str = "") -> str:
    net = ""
    pts = " ".join(f"{fx(ex(x))} {fx(ey(y))}" for x, y in points)
    return f"TRACK~{fx(width)}~{layer}~{net}~{pts}~{ids.next()}~0"


def pad_rect(x: float, y: float, w: float, h: float, net: str, number: str) -> str:
    net = ""
    x0, x1 = ex(x - w / 2), ex(x + w / 2)
    y0, y1 = ey(y - h / 2), ey(y + h / 2)
    points = f"{fx(x0)} {fx(y0)} {fx(x1)} {fx(y0)} {fx(x1)} {fx(y1)} {fx(x0)} {fx(y1)}"
    return (
        f"PAD~RECT~{fx(ex(x))}~{fx(ey(y))}~{fx(w)}~{fx(h)}~1~{net}~{number}~0~"
        f"{points}~0~{ids.next()}~0~~Y~0~0~0.4~{fx(ex(x))},{fx(ey(y))}"
    )


def pad_circle(x: float, y: float, diameter: float, net: str, number: str) -> str:
    net = ""
    return (
        f"PAD~ELLIPSE~{fx(ex(x))}~{fx(ey(y))}~{fx(diameter)}~{fx(diameter)}~1~{net}~{number}~0~~0~"
        f"{ids.next()}~0~~Y~0~0~0.4~{fx(ex(x))},{fx(ey(y))}"
    )


def rounded_outline() -> list[str]:
    pts = src.rounded_points(0, 0, src.CARD_W, src.CARD_H, src.CORNER_R, 24)
    return [track(10, 0.1, pts + [pts[0]])]


def photo_solids(img: Image.Image, layer: int) -> list[str]:
    bw = img.convert("L")
    w, h = bw.size
    px_w = src.CARD_W / w
    px_h = src.CARD_H / h
    pix = bw.load()
    shapes: list[str] = []

    for row in range(h):
        y_top = src.CARD_H - row * px_h
        y_bot = src.CARD_H - (row + 1) * px_h
        y_mid = (y_top + y_bot) / 2
        col = 0
        while col < w:
            while col < w:
                x_mid = (col + 0.5) * px_w
                if (
                    pix[col, row] > 127
                    and src.inside_card(x_mid, y_mid, src.EDGE_CLEARANCE)
                    and not src.in_component_keepout(x_mid, y_mid)
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
                    or not src.inside_card(x_mid, y_mid, src.EDGE_CLEARANCE)
                    or src.in_component_keepout(x_mid, y_mid)
                ):
                    break
                col += 1
            shapes.append(solid(layer, path_rect(start * px_w, y_bot, col * px_w, y_top)))
    return shapes


def back_silk_solids() -> list[str]:
    if not src.BACK_SILK_SRC.exists():
        return []
    img = Image.open(src.BACK_SILK_SRC).convert("L").resize((520, 520), Image.Resampling.LANCZOS)
    img = img.point(lambda p: 255 if p < 150 else 0)
    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    w, h = img.size
    scale = src.BACK_SILK_SIZE / max(w, h)
    draw_w = w * scale
    draw_h = h * scale
    x_origin = (src.CARD_W - draw_w) / 2
    y_origin = (src.CARD_H - draw_h) / 2
    pix = img.load()
    shapes: list[str] = []
    for row in range(h):
        y_top = y_origin + (h - row) * scale
        y_bot = y_origin + (h - row - 1) * scale
        y_mid = (y_top + y_bot) / 2
        col = 0
        while col < w:
            while col < w:
                x_mid = x_origin + (col + 0.5) * scale
                if pix[col, row] > 127 and src.inside_card(x_mid, y_mid, 1.4):
                    break
                col += 1
            if col >= w:
                break
            start = col
            while col < w:
                x_mid = x_origin + (col + 0.5) * scale
                if pix[col, row] <= 127 or not src.inside_card(x_mid, y_mid, 1.4):
                    break
                col += 1
            shapes.append(solid(4, path_rect(x_origin + start * scale, y_bot, x_origin + col * scale, y_top)))
    return shapes


def circuit_shapes() -> list[str]:
    shapes: list[str] = []
    antenna = [
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
    shapes.append(track(1, 0.45, antenna, "ANT"))

    for pts, net in [
        ([(75.8, 45.325), (76.6, 45.325), (76.6, 45.3), (77.55, 45.3)], "VOUT"),
        ([(75.8, 44.675), (76.6, 44.675), (76.6, 45.325)], "VOUT"),
        ([(78.45, 45.3), (79.15, 45.3)], "LED_A"),
        ([(80.05, 45.3), (80.65, 45.3)], "LED_K"),
        ([(77.55, 43.3), (76.6, 43.3), (76.6, 45.325)], "VOUT"),
        ([(70.6, 45.325), (68.8, 45.325), (68.8, 43.3), (79.15, 43.3)], "GND"),
        ([(81.55, 45.3), (81.55, 43.3), (80.05, 43.3)], "GND"),
        ([(70.6, 44.675), (64.0, 41.0)], "SCL"),
        ([(70.6, 44.025), (66.0, 41.0)], "FD"),
        ([(75.8, 44.025), (68.0, 41.0)], "SDA"),
        ([(76.6, 45.325), (70.0, 41.0)], "VOUT"),
        ([(68.8, 43.3), (72.0, 41.0)], "GND"),
    ]:
        shapes.append(track(1, 0.25, pts, net))

    # U1: NT3H2111W0FTTJ TSSOP-8. Pin map: 1 LA, 2 VSS, 3 SCL, 4 FD, 5 SDA, 6 VCC, 7 VOUT, 8 LB.
    for number, net, x, y in [
        ("1", "ANT", 70.6, 45.975),
        ("2", "GND", 70.6, 45.325),
        ("3", "SCL", 70.6, 44.675),
        ("4", "FD", 70.6, 44.025),
        ("5", "SDA", 75.8, 44.025),
        ("6", "VOUT", 75.8, 44.675),
        ("7", "VOUT", 75.8, 45.325),
        ("8", "ANT", 75.8, 45.975),
    ]:
        shapes.append(pad_rect(x, y, 0.56, 1.20, net, number))

    for number, net, x, y in [
        ("R1-1", "VOUT", 78.0, 45.3),
        ("R1-2", "LED_A", 79.6, 45.3),
        ("D1-A", "LED_A", 81.1, 45.3),
        ("D1-K", "GND", 82.7, 45.3),
        ("C1-1", "VOUT", 78.0, 43.3),
        ("C1-2", "GND", 79.6, 43.3),
    ]:
        shapes.append(pad_rect(x, y, 0.90, 0.80, net, number))

    for number, net, x, y in [
        ("TP-SCL", "SCL", 64.0, 41.0),
        ("TP-FD", "FD", 66.0, 41.0),
        ("TP-SDA", "SDA", 68.0, 41.0),
        ("TP-VOUT", "VOUT", 70.0, 41.0),
        ("TP-GND", "GND", 72.0, 41.0),
    ]:
        shapes.append(pad_circle(x, y, 1.10, net, number))
    return shapes


def make_project() -> None:
    OUT.mkdir(exist_ok=True)
    img = Image.open(src.SRC).resize((src.PHOTO_W, round(src.PHOTO_W * src.CARD_H / src.CARD_W)), Image.Resampling.LANCZOS)
    img = img.convert("L").point(lambda p: 255 if p >= 128 else 0)

    shapes: list[str] = []
    shapes.extend(rounded_outline())
    shapes.extend(photo_solids(img, 1))
    shapes.extend(photo_solids(img, 7))
    shapes.extend(circuit_shapes())
    shapes.extend(back_silk_solids())

    pcb = {
        "head": {
            "docType": "3",
            "editorVersion": "6.5.22",
            "newgId": True,
            "c_para": {},
            "hasIdFlag": True,
        },
        "canvas": f"CA~1000~1000~#000000~yes~#FFFFFF~10~1000~1000~line~0.5~mm~0.25~45~~0.5~{fx(OX + src.CARD_W / 2)}~{fx(OY + src.CARD_H / 2)}~0~yes",
        "shape": shapes,
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
        "objects": [
            "All~true~false",
            "Component~true~true",
            "Prefix~true~true",
            "Name~true~false",
            "Track~true~true",
            "Pad~true~true",
            "Via~true~true",
            "Hole~true~true",
            "Copper_Area~true~true",
            "Circle~true~true",
            "Arc~true~true",
            "Solid_Region~true~true",
            "Text~true~true",
            "Image~true~true",
            "Rect~true~true",
            "Dimension~true~true",
            "Protractor~true~true",
        ],
        "BBox": {"x": OX, "y": OY, "width": src.CARD_W, "height": src.CARD_H},
        "preference": {"hideFootprints": "", "hideNets": ""},
        "DRCRULE": {
            "Default": {"trackWidth": 0.25, "clearance": 0.15, "viaHoleDiameter": 0.6, "viaHoleD": 0.3},
            "isRealtime": False,
            "isDrcOnRoutingOrPlaceVia": False,
            "checkObjectToCopperarea": True,
            "showDRCRangeLine": True,
        },
        "netColors": {},
    }

    JSON_PATH.write_text(json.dumps(pcb, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(JSON_PATH, JSON_PATH.name)
        zf.write(Path("NFC功能版说明.md"), "NFC功能版说明.md")
        zf.write(src.OUT / "nfc_photo_card_proto_v1" / "NDEF_URL_programming.txt", "NDEF_URL_programming.txt")


if __name__ == "__main__":
    make_project()

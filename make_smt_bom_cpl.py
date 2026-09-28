from __future__ import annotations

import csv
from pathlib import Path

import make_nfc_photo_pcb_gerbers as pcb


OUT = Path("smt_order_files")


def scaled(x: float, y: float) -> tuple[float, float]:
    return pcb.sx(x), pcb.sy(y)


COMPONENTS = [
    {
        "designator": "U1",
        "comment": "NT3H2111W0FTTJ",
        "footprint": "TSSOP-8_L4.4-W3.0-P0.65-LS6.4-BR",
        "lcsc": "C2654884",
        "x": (70.6 + 75.8) / 2,
        "y": 45.0,
        "rotation": 0,
        "note": "NXP NTAG I2C plus 1K NFC tag, pin 1 at upper-left pad in board view",
    },
    {
        "designator": "R1",
        "comment": "330R",
        "footprint": "R0603",
        "lcsc": "C23138",
        "x": (78.0 + 79.6) / 2,
        "y": 45.3,
        "rotation": 0,
        "note": "LED current limit resistor",
    },
    {
        "designator": "D1",
        "comment": "LED_YELLOW_0603",
        "footprint": "0603",
        "lcsc": "C264455",
        "x": (81.1 + 82.7) / 2,
        "y": 45.3,
        "rotation": 0,
        "note": "Anode on left pad, cathode on right pad/GND; verify LED polarity in JLC preview",
    },
    {
        "designator": "C1",
        "comment": "220nF_X7R",
        "footprint": "C0603",
        "lcsc": "C7224448",
        "x": (78.0 + 79.6) / 2,
        "y": 43.3,
        "rotation": 0,
        "note": "VOUT reservoir capacitor",
    },
]


def main() -> None:
    OUT.mkdir(exist_ok=True)

    bom_path = OUT / "NFC_Photo_Card_BOM.csv"
    with bom_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"],
        )
        writer.writeheader()
        for c in COMPONENTS:
            writer.writerow(
                {
                    "Comment": c["comment"],
                    "Designator": c["designator"],
                    "Footprint": c["footprint"],
                    "LCSC Part #": c["lcsc"],
                }
            )

    cpl_path = OUT / "NFC_Photo_Card_CPL.csv"
    with cpl_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"],
        )
        writer.writeheader()
        for c in COMPONENTS:
            x, y = scaled(c["x"], c["y"])
            writer.writerow(
                {
                    "Designator": c["designator"],
                    "Mid X": f"{x:.3f}mm",
                    "Mid Y": f"{y:.3f}mm",
                    "Layer": "Top",
                    "Rotation": c["rotation"],
                }
            )

    readme = f"""SMT order files for NFC photo card

Board size used for coordinates: {pcb.CARD_W:.2f} x {pcb.CARD_H:.2f} mm
Coordinate origin: bottom-left of the Gerber board outline
Layer: all components are on Top

Files:
- NFC_Photo_Card_BOM.csv: BOM upload
- NFC_Photo_Card_CPL.csv: pick-and-place / component placement upload

Important checks in JLC SMT preview:
- U1 pin 1 should be on the upper-left pad of the TSSOP-8 footprint in board view.
- D1 LED anode should be on the left pad; cathode mark should face the right/GND pad.
- If JLC reports a part out of stock, keep the same footprint and substitute an equivalent part.
- After assembly, write the NDEF URL to U1 with NFC Tools or NXP TagWriter.
"""
    (OUT / "README_SMT.txt").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()

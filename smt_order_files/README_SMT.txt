SMT order files for NFC photo card

Board size used for coordinates: 114.05 x 70.00 mm
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

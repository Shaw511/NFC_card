NFC photo PCB card prototype v1

Function:
- Tap with a phone: NT3H2111 NFC tag opens this URL: https://c6.y.qq.com/base/fcgi-bin/u?__=kIR6N1TP7wer
- During RF field presence: VOUT harvests energy and lights a low-current LED.
- Front visual: gold photo pixels on black soldermask, with antenna mostly hidden under soldermask.
- Board size: 114.05 x 70.00 mm, scaled 1.3323x from 85.60 x 52.54 mm so the short side reaches 70.00 mm.

Layer mapping:
- nfc_photo_card.GKO: board outline
- nfc_photo_card.GTL: top copper photo pixels, NFC antenna, pads, and traces
- nfc_photo_card.GTS: top soldermask openings for photo gold pixels and component pads
- nfc_photo_card.GTP: top paste for SMT assembly
- nfc_photo_card.GBO: bottom silkscreen signature image from 背面小图 签名.png
- Bottom copper and bottom soldermask openings are intentionally empty.

Important:
- This is a manufacturable prototype, not a guaranteed tuned RF production antenna.
- After the first board, verify read range and LED behavior. If read range is poor, tune antenna capacitance or reduce LED load.
- Photo bitmap used: 800 x 491, mask opening runs: 15238
- Back silkscreen size: 58.6 x 58.6 mm, silk opening runs: 2150

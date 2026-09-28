# NFC 功能版说明

我选择的方案是 `NT3H2111W0FTTJ`，NXP NTAG I2C plus 1K，TSSOP-8 封装。

实现目标：

- 手机靠近时读取 NFC Tag，并弹出：
  `https://c6.y.qq.com/base/fcgi-bin/u?__=kIR6N1TP7wer`
- 手机靠近时，芯片 `VOUT` 能量采集输出给低电流 LED 供电，LED 会短暂点亮。
- 正面仍然是黑色阻焊 + 沉金照片效果。

## 已生成文件

- `nfc_photo_pcb_gerber/nfc_photo_card_proto_v1.zip`：NFC 功能版 Gerber 原型包。
- `nfc_photo_pcb_gerber/nfc_photo_card_proto_v1/BOM_and_order_notes.txt`：BOM 和下单参数。
- `nfc_photo_pcb_gerber/nfc_photo_card_proto_v1/NDEF_URL_programming.txt`：URL 的 NDEF 写入字节。
- 背面丝印层 `nfc_photo_card.GBO` 已加入 `背面小图 签名.png`，居中约 44 mm x 44 mm。

## 器件

- U1：`NT3H2111W0FTTJ`，NXP NTAG I2C plus 1K，TSSOP-8
- R1：330 ohm，0603
- D1：0603 黄光/琥珀色低电流 LED，优先选 Vf <= 2.0 V
- C1：220 nF，0603，X7R

## 下单参数

- 2 层板
- 黑色阻焊
- 沉金 / ENIG
- 0.8 mm 或 1.0 mm 板厚
- 1 oz 铜厚

## 编程方式

贴好 U1 后，用 NFC Tools 或 NXP TagWriter 写入 URL 即可。也可以把 `NDEF_URL_programming.txt` 交给支持预写入的贴片/烧录服务。

## 风险提示

这是可制造的第一版 NFC 原型，不是已经实测调谐过的量产天线。照片里的大量金属铜岛、LED 负载、手机型号和板厚都会影响读取距离。第一批建议先打样 5 片，确认读距和 LED 亮度后再批量生产。

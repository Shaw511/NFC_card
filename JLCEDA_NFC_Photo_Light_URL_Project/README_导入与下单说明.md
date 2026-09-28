# 嘉立创 EDA NFC 沉金照片亮灯卡

## 文件

- `NFC_Photo_Light_URL_EasyEDA_Std_Project.zip`：嘉立创 EDA 标准版 PCB 工程压缩包，优先导入这个。
- `NFC_Photo_Light_URL_EasyEDA_Std_PCB.json`：如果 ZIP 导入失败，导入这个单 PCB JSON。
- `NFC_Photo_Light_URL_Gerber.zip`：Gerber 生产文件。
- `BOM.csv` / `CPL.csv`：SMT 贴片参考文件。
- `NDEF_URL_programming.txt`：把网址写进 NFC 芯片的字节。

## 设计约束

- 正面照片使用 `PCB_黑白双色_保细节抖动版.png`：白色像素在 TopLayer 铺铜并在 TopSolderMaskLayer 开窗，黑色像素不开窗；下单选择黑色阻焊 + 沉金后，白色区域露出沉金。
- NFC 天线、U1 芯片、C1 储能电容和 5 个测试点移到底层/背面，避免正面天线框遮挡人像。
- 正面右上角只保留 R1 限流电阻和 D1 LED，通过两个 0.3 mm 金属化过孔连接到底层 VOUT/GND。
- 背面签名使用 `背面小图 签名.png`，放在 BottomSilkLayer，已做背面镜像处理。
- D1 通过 U1 的 VOUT 能量采集输出点亮；手机靠近时读取 U1 内的 NDEF URL。

## 下单建议

- 2 层板，黑色阻焊，沉金 / ENIG，1 oz 铜。
- 0.8 mm 或 1.0 mm 更像卡片；需要贴片稳定性可选 1.6 mm。
- 这是未实测调谐的第一版 NFC 原型。正面照片铜皮仍会影响底层天线读距，首批建议小批量打样后按读距调整天线或减少照片铜面积。
- 如果嘉立创贴片不支持本单的双面贴装组合，可选择只贴正面 LED/R1，背面 U1/C1 手焊，或反过来按装配能力调整元件面。

## 写入网址

目标 URL：`https://c6.y.qq.com/base/fcgi-bin/u?__=kIR6N1TP7wer`

贴片后可用 NFC Tools、NXP TagWriter 或量产烧录服务写入 `NDEF_URL_programming.txt` 中的内容。

生成信息：板尺寸 114.05 mm x 70.00 mm；正面照片开窗 run 数 23297；背面丝印 run 数 2150。

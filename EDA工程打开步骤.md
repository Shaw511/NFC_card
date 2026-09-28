# 嘉立创 EDA 工程打开步骤

我已经生成了可导入嘉立创 EDA 的标准版 PCB JSON/ZIP：

- `easyeda_std_project/NFC_Photo_Card_EasyEDA_Std_Project.zip`
- `easyeda_std_project/NFC_Photo_Card_EasyEDA_Std_PCB.json`

## 专业版打开方式

1. 打开嘉立创 EDA 专业版。
2. 在开始页找“迁移标准版”，或在菜单里选择“导入 - 嘉立创EDA(标准版)”。
3. 选择 `easyeda_std_project/NFC_Photo_Card_EasyEDA_Std_Project.zip`。
4. 导入后打开 PCB，检查这些层：
   - BoardOutLine：圆角卡片板框
   - TopLayer：照片铜、NFC 天线、焊盘、走线
   - TopSolderMaskLayer：正面沉金照片开窗
   - BottomSilkLayer：背面签名丝印
5. 从 EDA 的 PCB 下单入口提交，工艺选择黑色阻焊、沉金、2 层、0.8 mm 或 1.0 mm。

## 如果 ZIP 导入失败

改选单个 JSON 文件：

`easyeda_std_project/NFC_Photo_Card_EasyEDA_Std_PCB.json`

专业版官方说明：在已打开工程时，可以导入嘉立创 EDA 标准版的单个 JSON 文件，导入后会插入当前工程。

## 注意

这个工程是为了从 EDA 入口下单和后续修改而生成的可编辑 PCB 图元版本。下单前仍要看一遍 Gerber/3D 预览，确认背面丝印方向、正面照片、板框和焊盘都正常。

# 全息茶餐厅招牌贴图生成器（立式 + 壁挂）

`generate_holo_signboard.py` 使用纯本地 Python + Pillow 程序化生成两套建筑的全部 18 张 RGBA PNG：立式 2×1「全息茶餐厅加盟招牌」与壁挂 1×1「壁挂全息茶餐厅招牌」。无需网络、付费 API、numpy、原模组贴图或外部插画；中文字体来自本机 `C:\Windows\Fonts`。

## 重新生成

在仓库根目录执行：

```bash
py -3.15 Tools/HoloSignboard/generate_holo_signboard.py
```

也可使用安装了 Pillow 11+ 的其他 Python 3.13+ 解释器。脚本中的固定随机种子保证米粒、葱花、炸衣颗粒和叉烧焦斑可重复生成。所有图形先在 3x/4x 超采样画布绘制，再以 Lanczos 缩小。半透明图元会先画到局部图层再 `alpha_composite`（Pillow 直接在 RGBA 图上画半透明色会“替换”而非混合像素，会把食物和面板打穿）。

输出目录：

```text
Textures/Things/Building/HoloSignboard/          （立式 2×1）
├── HoloSignboardBase_{south,north,east,west}.png
├── HoloSignboardHologram_{south,north,east,west}.png
└── HoloSignboard_UI.png
Textures/Things/Building/WallHoloSignboard/      （壁挂 1×1）
├── WallHoloSignboardBase_{north,south,east,west}.png      256×256
├── WallHoloSignboardHologram_{north,south,east,west}.png  1024×1024
└── WallHoloSignboard_UI.png                               1024×1024
```

## 立式招牌：全息层与底座发射槽对齐

已检查 CeleTech `TradeInfoConsole` 原图、Alpha 通道及 `CommTower.xml`：底座 `640×384 / drawSize (2.4,1.6)`，全息层 `1024×1024 / drawSize 3.8 / 南北偏移 (0,0,0.73)`。

按真实世界坐标换算（`texture_report.json` 的 `anchors.standing` 由脚本实时计算）：

| 项目 | 数值 |
|---|---|
| 底座黑色发射槽 | 底座行 `174–211` → 世界 z `+0.075 ~ −0.079` |
| 对应全息层行 | `≈ 689–730` |
| 面板主体底边 | 行 `676`（此前硬切在 `690`，正好停在槽口上沿） |
| 梯形投影裙边 | 行 `670 → 718`，上宽 `327–697`、下收至 `345–679`（落在槽宽 `335–693` 内） |
| 最亮发射线 | 行 `717`，位于槽内 |
| 底部羽化 | 行 `717 → 748` 线性渐隐，Alpha 在 `743` 归零；裁剪框 `(296,140)-(728,752)` |

`verify_standing.png` 把底座按 `2.4×1.6` 放在 `(0,0)`、全息层按 `3.8×3.8` 放在 `(0,0.73)` 合成，右侧并排放大“仅底座 / 底座 + 全息”的槽口区域，可直接看到光束插进槽内。

全息涂层：外侧辉光只画在面板外（不再叠在底板下面把它“垫实”），底板 Alpha 自上而下 `165 → 116` 且中心再减薄约 `35`，叠加明暗交替扫描线、蜂窝网格、柔和扫描带和向内渐隐的边缘辉光；菜单卡是 Alpha `136` 的深色透视窗口。标题、菜品与按钮保持不透明。

## 壁挂招牌

### 朝向约定（与原版一致）

原版 `Placeworker_AttachedToWall` 要求 `loc + rot.FacingCell` 是墙（反编译确认），原版 `WallLamp_north` 也把灯画在贴图下部、配合 `drawOffsetNorth (0,0,0.9)` 落在北墙面上。因此：

| 贴图 | 旋转 | 墙的位置 | 画面 |
|---|---|---|---|
| `_north` | Rot North | 北墙 | 正面完整大菜单，从墙面发射器向上投射 |
| `_south` | Rot South | 南墙 | 背面：镜像、稍扁、更通透 + 绿/夕阳红背光 |
| `_east` | Rot East | 东墙 | 侧面：约 55° 转角的透视光幕从墙上竖向发射条向西伸出 |
| `_west` | Rot West | 西墙 | 与 `_east` 几何镜像，但文字仍正向可读 |

### 与 XML 偏移的对齐（`anchors.wall`）

底座 `drawSize (1,1)`、偏移 `N(0,0,0.9) / S(0,0,−0.9) / E(0.9,0,0) / W(−0.9,0,0)`；全息层 `drawSize 2.6`、`TransparentPostLight`、偏移 `N(0,0,1.25) / S(0,0,−0.35) / E(0.55,0,0.45) / W(−0.55,0,0.45)`。

| 朝向 | 底座发射槽 | 换算到全息层 | 全息层设计 |
|---|---|---|---|
| North | 行 `141–145`（z≈0.841） | 行 `≈673` | 梯形光束下沿 `412–612 @ 672` |
| South | 行 `10–15`（z≈−0.449） | 行 `≈551` | 光束下沿 `412–612 @ 552` |
| East | 列 `11–16`（x≈0.453） | 列 `≈474`，行 `557–738` | 竖向发射线 `x=473, y=556–736` |
| West | 东侧的镜像 | 列 `≈550` | 同上镜像 |

若 XML 偏移调整，修改脚本顶部 `WALL_*_OFFSETS` 常量后重新生成即可让 `preview_wall.png` 重新核对。

### 画面内容

- 亮绿全息底板 + 夕阳红「茶餐厅」金边立体艺术字，副标「主厨首推 · 黯然销魂」。
- 主菜「黯然销魂饭」：港式公鸡碗（钴蓝口沿、红公鸡、芭蕉叶纹）、逐粒白米饭、渗入米饭的甜豉油汁、五片厚切蜜汁叉烧（焦边、红亮釉面、粉色切面与肥膘纹）、流心太阳蛋、两棵菜心、紫洋葱圈与葱花、热气。
- `CHAR SIU & SUNNY EGG RICE`、`$58 PER BOWL` 价签、夕阳红「点单 +」按钮、`No.1 招牌` 角标。
- 底座：粗黑轮廓 + 银灰金属壳 + 深色绿光发射槽 + `ICCT / 茶餐厅` 小铭牌，风格与立式底座统一。

## 验收辅助文件

脚本同时在本目录生成：

- `preview.png`：两套共 18 张贴图的接触表。
- `verify_standing.png`：立式招牌世界坐标合成验证图（含槽口放大对比）。
- `preview_wall.png`：壁挂四朝向世界坐标合成（含墙格与占用格标记）+ 原始贴图。
- `tomato_zoom.png`、`curry_zoom.png`、`title_zoom.png`：立式菜品与标题 4 倍放大。
- `wall_bowl_zoom.png`、`wall_menu_zoom.png`：黯然销魂饭插画与菜单排版 3 倍放大。
- `texture_report.json`：每张输出的尺寸、Alpha bbox、透明/半透明/不透明像素数、覆盖率、SHA-256，以及 `anchors` 对齐数据。

## 离线验证（`run-qa.ps1` / `HoloSignboard.cs`）

运行 `pwsh -File Tools/HoloSignboard/run-qa.ps1` 可执行包含既有 706 项与本功能 93 项在内的全部 799 项离线检查：

- 建筑与思想 XML、严格中英文文本与 Keyed/DefInjected 注入；
- 四朝向交互格与原生寻路、南北 `(0,0,0.73)` 与东西贴图内建对齐偏移、生产绘制 IL；
- 供电/开关/太阳耀斑门控、阵营限制、Gizmo 免小人直接打开点单窗口及购买、小人右键走过去交互及抵达开窗、居住区白银扣款、原版空投舱送货；
- `ThoughtWorker_SawStrangeSignboard` 在 10 格范围内且 `GenSight.LineOfSight` 畅通时对 `TorturedArtist` 生效（`-6`），距离外、隔墙、非该特质、失明、睡眠、断电及离图立即返回 `Inactive`。

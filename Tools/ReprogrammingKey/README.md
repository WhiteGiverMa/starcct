# 重构密钥贴图生成

`generate_reprogramming_key.py` 是「重构密钥」`ReprogrammingKey.png` 的唯一生成入口，依赖 Python 标准库与 Pillow，无外部图片或字体依赖。已实际使用 **Python 3.15.2 / Pillow 13.0.0**；也兼容 Python 3.13 / Pillow 11。仓库路径由 `__file__` 定位。

字节级复现请使用上述 Python 3.15.2 / Pillow 13.0.0 组合。脚本无随机数，同一环境重复运行输出解码后像素与 SHA256 均相同。

从仓库根目录运行：

```powershell
py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py --help
py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py
```

## 画的是什么

参考《逃离塔科夫》实验室高级门禁房卡，重新配色为环世界超凡科技（Archotech）的灰翠绿卡身与暖金黄点缀：

- 约 `-31°` 斜放的圆角卡身，纯黑轮廓约 `1.1` 设计单位（256 像素下约 `4.4px`），左上主光、右下窄幅中翠暗边（不与黑描边叠成双层粗边）。
- 左端内凹挂绳槽、正面金色智能芯片触点、芯片右侧超凡几何走线与发光节点、六边形徽记、微缩数据块、底部深色磁条、右端带双折角的金色识别色带。
- 卡面留白足够，在 64×64 游戏等效尺寸与 256×256 原生尺寸下都能直接认出是一张高级门禁卡。

## 分辨率与抗锯齿

贴图为 **256×256**（与 DMS 门禁卡同规格）。`Graphic_Single` 无论 64 还是 256 像素都缩放到 1 格，256 提供 4 倍线密度。

几何在 64 单位设计空间中绘制，以每单位 32 像素超采样到 2048×2048，再用 Lanczos 缩到 256×256：

- RGB：卡面画在不透明纯黑底上后单独缩放，卡身与黑描边之间的内边缘同样平滑。
- Alpha：外轮廓遮罩单独 Lanczos 缩放，保留平滑过渡；`alpha < 8` 归零、`alpha > 248` 归 255 以去除振铃。
- 所有 `0 < alpha < 255` 的像素都位于纯黑描边带内，RGB 强制为 `(0,0,0)`；透明像素同样 RGB 全零。因此 RimWorld 的 Cutout（`alpha ≥ 0.5`）与 UI 混合都不会出现亮色光晕。

## 隔离再生与验证

预览与报告放在 Temp，勿放进运行贴图文件夹。以下命令在 Windows PowerShell / pwsh 中运行：

```powershell
$qa = Join-Path $env:LOCALAPPDATA 'Temp/opencode/starcct-reprogramming-key-qa'
New-Item -ItemType Directory -Force $qa | Out-Null
$env:PYTHONPYCACHEPREFIX = Join-Path $qa 'pycache'
py -3.15 -m py_compile Tools/ReprogrammingKey/generate_reprogramming_key.py
py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py --output "$qa/run1.png" --preview "$qa/preview.png" > "$qa/run1.json"
py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py --output "$qa/run2.png" > "$qa/run2.json"
$one = (Get-FileHash "$qa/run1.png" -Algorithm SHA256).Hash
$two = (Get-FileHash "$qa/run2.png" -Algorithm SHA256).Hash
if ($one -ne $two) { throw 'Non-deterministic image' }
```

每次生成都会检查：256×256 RGBA；透明像素 RGB 全零（`transparent_rgb_nonzero == 0`）；半透明像素 RGB 全黑（`semitransparent_nonblack == 0`）；`alpha > 0` 的 4 连通主体只有 1 个；剪影不贴画布边缘。标准输出给出 alpha 范围与级数、半透明像素数、bbox、按 alpha 加权的覆盖率与 SHA256。

预览在深色和浅色棋盘背景下并排展示：64×64 游戏等效尺寸、256×256 原生尺寸、卡片下长边的 6 倍最近邻局部放大。可加 `--before 旧贴图.png` 在最前面附上旧图的同尺寸视图与同位置放大，做前后对照。

## 与游戏的关系

运行贴图路径为 `Textures/Things/Item/Special/ReprogrammingKey.png`，对应 `Defs/ThingDefs/AyameICCT_Items_Reprogramming.xml` 的 `<texPath>Things/Item/Special/ReprogrammingKey</texPath>` 与 `Graphic_Single`。这是单图物品，不需要堆叠档位或 `_m` 遮罩。

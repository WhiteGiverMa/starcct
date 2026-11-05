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

- 约 `-31°` 斜放的圆角卡身，纯黑轮廓约 `1.9px`，左上主光、右下翡翠暗部。
- 左端内凹挂绳槽、正面金色智能芯片触点、芯片右侧超凡几何走线与发光节点、六边形徽记、微缩数据块、底部深色磁条、右端带双折角的金色识别色带。
- 卡面留白足够，在 `1x`（64×64）与 `4x`、`6x` 最近邻放大下都能直接认出是一张高级门禁卡。

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

每次生成都会检查 64×64 RGBA、alpha 仅 `{0,255}`、透明 RGB 全零、单一连通主体、剪影不贴画布边缘，并向标准输出给出 bbox、覆盖率与 SHA256。预览包含 `1x`/`4x`/`6x` 在深色和浅色棋盘背景下的对照。

## 与游戏的关系

运行贴图路径为 `Textures/Things/Item/Special/ReprogrammingKey.png`，对应 `Defs/ThingDefs/AyameICCT_Items_Reprogramming.xml` 的 `<texPath>Things/Item/Special/ReprogrammingKey</texPath>` 与 `Graphic_Single`。这是单图物品，不需要堆叠档位或 `_m` 遮罩。

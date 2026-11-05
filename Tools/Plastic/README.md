# 塑料开发材料与贴图生成

## 当前入口

`generate_granule_bags.py` 是全部 **八张** 塑料贴图（`PlasticGranule_{a,b,c,d}`、`PlasticSheet_{a,b,c,d}`）的唯一生成入口，依赖 Python 标准库与 Pillow。已实际使用 **Python 3.15.2 / Pillow 13.0.0**；也兼容 Python 3.13 / Pillow 11。完全自包含：不读取任何外部图片、字体，也不导入 `history/` 中的脚本；仓库路径由 `__file__` 定位。文件名沿用旧名，以免既有引用失效。

字节级复现请使用上述 Python 3.15.2 / Pillow 13.0.0 组合。脚本只用固定种子，同一环境重复运行输出 SHA256 相同。

从仓库根目录运行：

```powershell
py -3.15 Tools/Plastic/generate_granule_bags.py --help
py -3.15 Tools/Plastic/generate_granule_bags.py
```

默认写入 `Textures/Things/Item/Resource/PlasticGranule/PlasticGranule_{a,b,c,d}.png` 与 `Textures/Things/Item/Resource/PlasticSheet/PlasticSheet_{a,b,c,d}.png`，沿用 `Graphic_StackCount` 文件夹加载方式。传 `--output-dir <目录>` 时八张平铺写入该目录，不碰运行贴图。

| 贴图 | 内容 | 设计来源（已移植进当前脚本） |
|---|---|---|
| `PlasticGranule_a` | 一只零碎五金包装大小的密封小袋 | 原 `pouch()` |
| `PlasticGranule_b` | 三只与 `_a` 同尺寸的小袋，松散交叠 | 原 `pouch()` |
| `PlasticGranule_c` | 三只线性 **1.6 倍**大袋，错位叠放 | 原 `pouch()` |
| `PlasticGranule_d` | 敞口食品级周转箱，装满颗粒，卷边箱口 | `history/.../pk-gpt` 的 `granules_c()` |
| `PlasticSheet_a` | 三张交叠散膜，一角翻起 | `pk-gpt` 的 `sheets_a()` |
| `PlasticSheet_b` | 约十层膜片叠成一摞 | `pk-gpt` 的 `sheets_b()`，保持此前缩到 75% 后的外形框 |
| `PlasticSheet_c` | 用掉一半的斜放膜卷，露出前缘 | 原 Temp 中 `small_roll(extension=10)`，旋转 27° |
| `PlasticSheet_d` | 大号横放膜卷，同心卷层与膜舌 | `pk-gpt` 的 `sheets_c()` |

两组覆盖率都严格满足 `a < b < c < d`（按 alpha 加权）。`PlasticSheet_c` 此前比 `_b` 还小，本次放大到介于 `_b` 与 `_d` 之间。

## 256×256 抗锯齿规格

贴图为 **256×256 RGBA**。`Graphic_Single`/`Graphic_StackCount` 不论 64 还是 256 像素都缩放到 1 格，256 提供 4 倍线密度，消除了旧 64×64 二值 alpha 的楼梯边与马赛克颗粒。

- 几何在 64 单位设计空间中绘制，以每单位 32 像素超采样到 2048×2048，再用 Lanczos 缩到 256×256。
- 周转箱与膜材按原外形框整体等比缩放（`JOBS` 中的 `fit` 框，单位为 64 格坐标，含轮廓），保留原构图与尺度；袋装三档直接用原 64 格布局。
- 外轮廓：在高分辨率剪影上做**圆形**膨胀生成纯黑描边（约 0.6–1.1 单位，即 256 下约 2.5–4.5px；袋子与膜片已有内描边的档位外扩较少，使总黑边约 1.1–1.2 单位），不再用方形 `MaxFilter`，转角圆润。封闭的透明小洞自动填成黑色。
- RGB 先合成到不透明纯黑底上再单独 Lanczos 缩放；alpha 由外轮廓遮罩单独 Lanczos 缩放，`alpha < 8` 归零、`alpha > 248` 归 255，并限制在真实覆盖范围内以去除振铃杂点。
- 所有 `0 < alpha < 255` 的像素 RGB 强制为 `(0,0,0)`，透明像素 RGB 全零。因此 RimWorld 的 Cutout（`alpha ≥ 0.5`）与 UI 混合都不会出现亮色光晕。

## 隔离再生与验证

预览与报告放在 Temp，勿放进运行贴图文件夹。以下命令在 Windows PowerShell / pwsh 中运行（单次约 40 秒）：

```powershell
$qa = Join-Path $env:LOCALAPPDATA 'Temp/opencode/starcct-plastic-qa'
New-Item -ItemType Directory -Force $qa | Out-Null
$env:PYTHONPYCACHEPREFIX = Join-Path $qa 'pycache'
py -3.15 -m py_compile Tools/Plastic/generate_granule_bags.py
py -3.15 Tools/Plastic/generate_granule_bags.py --output-dir "$qa/run1" --preview "$qa/preview.png" > "$qa/run1.json"
py -3.15 Tools/Plastic/generate_granule_bags.py --output-dir "$qa/run2" > "$qa/run2.json"
foreach ($family in 'PlasticGranule', 'PlasticSheet') {
    foreach ($tier in 'a', 'b', 'c', 'd') {
        $name = "${family}_$tier.png"
        $one = (Get-FileHash "$qa/run1/$name" -Algorithm SHA256).Hash
        $two = (Get-FileHash "$qa/run2/$name" -Algorithm SHA256).Hash
        if ($one -ne $two) { throw "Non-deterministic image: $name" }
    }
}
```

每次生成都会检查每张图：256×256 RGBA；`transparent_rgb_nonzero == 0`；`semitransparent_nonblack == 0`；`alpha ≥ 128` 与 `alpha > 0` 下的 4 连通主体都只有 1 个；剪影不贴画布边缘；两组覆盖率严格递增。标准输出给出 alpha 范围与级数、半透明像素数、bbox、覆盖率与 SHA256。

预览每行一张贴图，在深色与浅色棋盘背景下展示：256 原生、64 游戏等效尺寸、轮廓上缘的 3 倍局部放大。`--before-dir <目录>` 可加入旧贴图（目录内平铺八张同名 PNG），并给出同尺寸视图与同位置放大做前后对照；须与 `--preview` 一起使用。数值检查不代替打开预览核对尺度与细节。

## 历史材料

`history/plastic-mod/` 从原 `~/rimmaid/plastic-mod/` 保留全部 26 个源文件、设计稿和资产（不含 Python 缓存）。公开版本仅将文档和脚本说明中的本机私有路径、私人称呼替换为通用写法；其余内容、资产和生成逻辑保持原样。包含原始方案以及 `pk-gpt`、`pk-glm` 两种艺术变体，各自的六张资产和预览均保留。`history/STATUS-plastic-excerpt.md` 仅摘录原工作区状态中相关的塑料历史；没有搬入整份工作区状态或其他模组资料。

**整个 `history/` 都是历史快照，不是当前数值规格或发布流程。** `draft.md`、`DESIGN-recipes.md` 的单位、质量、价格、配方及其“最终/固定”措辞只代表当时讨论。当前游戏实现以仓库 `Defs/`、`Source/` 为准。历史文档里的旧驱动器、游戏和 Temp 路径仅是当时证据位置，不是当前生成器依赖。

历史脚本用途：

| 脚本 | 历史用途 |
|---|---|
| `history/plastic-mod/gen_textures.py` | 初版三档、六文件生成器；旧基础绘图方法 |
| `history/plastic-mod/pk-gpt/gen_textures.py` | GPT 艺术变体；旧 `_c` 箱装后来成为发布 `_d` |
| `history/plastic-mod/pk-glm/gen_textures.py` | GLM 艺术变体，完整保留供对照 |

**旧根生成器 `main()` 有危险的六文件清理逻辑：会删除输出目录中不在旧六文件名单内的 PNG，包括当前 `_d`。不得把它的 `OUT_DIR` 改到当前运行贴图目录。** 历史脚本可供阅读与追溯，不作为当前再生/验收命令。以前 Temp 中的临时三档检查器和部署脚本没有纳入当前流程。

历史脚本只供阅读追溯；当前八张贴图由 `generate_granule_bags.py` 独立重绘，不依赖它们。

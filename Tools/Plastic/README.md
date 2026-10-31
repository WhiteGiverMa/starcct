# 塑料开发材料与贴图生成

## 当前入口

`generate_granule_bags.py` 是当前粒材袋装贴图的唯一生成入口，依赖 Python 标准库与 Pillow。已实际使用 **Python 3.15.2 / Pillow 13.0.0**；也兼容 Python 3.13 / Pillow 11。无外部图片、字体或历史脚本运行依赖，仓库路径由 `__file__` 定位。

字节级复现请使用上述 Python 3.15.2 / Pillow 13.0.0 组合。实测旧 Python 3.13 / Pillow 11 输出解码后的 RGBA 像素完全相同，但 PNG 压缩结果及文件 SHA256 不同。

从仓库根目录运行：

```powershell
py -3.15 Tools/Plastic/generate_granule_bags.py --help
py -3.15 Tools/Plastic/generate_granule_bags.py
```

默认只写 `Textures/Things/Item/Resource/PlasticGranule/PlasticGranule_{a,b,c}.png`。`_d` 箱装及全部四张 PlasticSheet 保持原文件；运行资源仍是两组各四张、总计八张 PNG，沿用 `Graphic_StackCount` 文件夹加载方式。

- `_a`：一只零碎五金包装大小的小密封袋。
- `_b`：三只与 `_a` 相同尺寸的小袋，松散交叠。
- `_c`：三只线性尺寸为小袋 **1.6 倍**的大袋，错位叠放，露出各自封口与侧边。整个袋堆显著小于 `_d`。
- 采用固定随机种子、8 倍超采样、RGB 抗锯齿、二值 cutout alpha；透明像素 RGB 清零。封口双线、冷青薄膜、乳白颗粒、褶皱高光与纯黑轮廓均由程序绘制。

## 隔离再生与验证

预览与报告放在 Temp，勿放进运行贴图文件夹。以下命令在 Windows PowerShell / pwsh 中运行：

```powershell
$qa = Join-Path $env:LOCALAPPDATA 'Temp/opencode/starcct-plastic-bags-qa'
New-Item -ItemType Directory -Force $qa | Out-Null
$env:PYTHONPYCACHEPREFIX = Join-Path $qa 'pycache'
py -3.15 -m py_compile Tools/Plastic/generate_granule_bags.py
py -3.15 Tools/Plastic/generate_granule_bags.py --output-dir "$qa/run1" --preview "$qa/preview.png" --preview-zoom 6 > "$qa/run1.json"
py -3.15 Tools/Plastic/generate_granule_bags.py --output-dir "$qa/run2" > "$qa/run2.json"
foreach ($tier in 'a', 'b', 'c') {
    $name = "PlasticGranule_$tier.png"
    $one = (Get-FileHash "$qa/run1/$name" -Algorithm SHA256).Hash
    $two = (Get-FileHash "$qa/run2/$name" -Algorithm SHA256).Hash
    if ($one -ne $two) { throw "Non-deterministic image: $name" }
}
```

每次生成都会检查 64×64 RGBA、alpha 仅 `{0,255}`、透明 RGB 全零、单一连通主体与 `a < b < c < d` 覆盖率，并向标准输出给出 bbox、覆盖率和 SHA256。预览包含四档并列的原尺寸及 4×/6×最近邻放大，在深色和浅色棋盘背景下观察。`--before-dir <目录>` 可额外加入修改前四张粒材 PNG 的对比；该目录内须是平铺的 `PlasticGranule_a.png` 到 `_d.png`，并与 `--preview` 一起使用。数值检查不代替打开预览核对袋子尺度、封口与叠层。

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

本次只做源材料迁移与离线贴图绘制/检查，未启动游戏。

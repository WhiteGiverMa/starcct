# 肠粉 / 猪肠粉堆叠贴图

`generate_changfen.py` 是七张贴图的自包含、确定性生成入口。只依赖 Python 标准库和 Pillow，不读取外部图片、字体或其他生成器。已验证 **Python 3.15 / Pillow 13.0.0**；代码兼容 Python 3.13+ / Pillow 11+。相同环境重复运行 PNG 字节一致。

设计依据为 `Docs/draft/changfen.md`：所有粉条均为斋食，**没有馅料、配菜、葱花、酱汁或酱汁包**。

## 生成

在仓库根目录运行：

```powershell
py -3.15 Tools/Changfen/generate_changfen.py --help
py -3.15 Tools/Changfen/generate_changfen.py
```

默认写入以下两个 `Graphic_StackCount` 目录，每个目录只包含运行时 PNG：

- `Textures/Things/Item/Meal/Changfen/Changfen_{a,b,c,d}.png`
- `Textures/Things/Item/Meal/ZhuChangfen/ZhuChangfen_{a,b,c}.png`

`--output-dir <目录>` 将七张图平铺写入指定目录。`--preview <文件.png>` 生成深浅棋盘上的 256px 原生视图、64px 游戏等效视图、3× 局部放大；预览必须位于 `Textures/` 和 `--output-dir` 之外。标准输出为逐张检查结果和 SHA256 的 JSON。

## 美术设计

| 贴图 | 内容 | Alpha 加权覆盖率 |
|---|---|---:|
| `Changfen_a` | 一只敞口食品级 PP 餐盒，四条柔软折叠式斋肠粉 | 18.356% |
| `Changfen_b` | 两只错位叠放的餐盒，均可看见白色肠粉 | 33.599% |
| `Changfen_c` | 有翻开箱盖的小纸箱，内装餐盒，旁边另放一盒 | 46.467% |
| `Changfen_d` | 大号封闭运输纸箱、封箱胶带、餐盒粉条标签、向上标记 | 48.070% |
| `ZhuChangfen_a` | 居中交叠的三小条白色猪肠粉，短而纤细，端面是连续螺旋 | 5.652% |
| `ZhuChangfen_b` | 敞口 PP 餐盒内整齐排列四卷猪肠粉，右下贴暖黄色便签及深色 `~~` 涂鸦 | 22.741% |
| `ZhuChangfen_c` | 比肠粉大箱更紧凑的小封闭纸箱，独立卷粉图标标签 | 29.311% |

肠粉使用平缓 Bezier 曲线绘制不规则薄片外缘、折叠唇和光泽；猪肠粉使用圆柱明暗及真正的连续螺旋端面。餐盒以冷白、灰青的叠色、双层模压边缘、卡扣和细筋表现半透明 PP 材质。纸箱使用较暖的牛皮纸色、清晰接缝、封箱胶带和无需字体的图示标签。

小纸箱与旁边餐盒有实际重叠，散卷之间也相互接触；两种构图均为单一连通剪影。

猪肠粉单份 `_a` 使用长度 12–14、半径 1.9–2.05 设计单位的三小条粉卷，较初版长度缩短约三分之一、粗细减少约四成，居中紧凑交叠，体现少量食物的尺度。保留螺旋端面和柔白高光，轮廓覆盖率由 13.719% 降为 5.652%。

猪肠粉盒的便签使用暖黄色纸面、轻微投影和折角，手绘式双波浪线在 64px 等效视图中仍可见，用来与单盒肠粉快速区分。便签完全落在餐盒原有剪影内部，不改变覆盖率。

## 与现有贴图一致的抗锯齿流程

几何、圆形膨胀、黑底合成及预览辅助函数移植自 `Tools/Plastic/generate_granule_bags.py`；不在运行时导入它。处理与 `Tools/ReprogrammingKey/generate_reprogramming_key.py` 的黑色消光边缘规则一致。

1. 64×64 设计空间，每单位 32 像素，绘制为 **2048×2048**。
2. 最终轮廓以圆周位移并集做 **1.1 设计单位圆形膨胀**，约 4.4 输出像素；餐盒局部重叠描边额外 0.1 单位。
3. 高分辨率剪影的封闭透明孔填成黑色。
4. RGB 先在不透明纯黑底上合成，再以 Lanczos 缩为 **256×256**；alpha 单独 Lanczos 缩放。
5. `alpha < 8` 归零，`alpha > 248` 归 255；BOX 覆盖遮罩抑制轮廓外振铃杂点。
6. 所有 `alpha < 255` 像素 RGB 强制纯黑，输出 **RGBA**。

每次生成在写入之前自动检查：

- `transparent_rgb_nonzero == 0`；`semitransparent_nonblack == 0`。
- `alpha > 0` 与 `alpha >= 128` 下分别恰好一个 **4 连通**前景区域。
- 两种阈值下均无封闭透明小孔；有完全透明和完全不透明像素。
- 外形不接触画布边界。
- 两个系列分别严格满足 `a < b < c [< d]` 的 alpha 加权覆盖率。

## 隔离复现与验收

```powershell
$qa = Join-Path $env:LOCALAPPDATA 'Temp/opencode/starcct-changfen-tex-qa'
New-Item -ItemType Directory -Force $qa | Out-Null
py -3.15 Tools/Changfen/generate_changfen.py --output-dir "$qa/run1" --preview "$qa/preview.png" > "$qa/run1.json"
py -3.15 Tools/Changfen/generate_changfen.py --output-dir "$qa/run2" > "$qa/run2.json"
foreach ($file in Get-ChildItem "$qa/run1/*.png") {
    $other = Join-Path "$qa/run2" $file.Name
    if ((Get-FileHash $file.FullName -Algorithm SHA256).Hash -ne (Get-FileHash $other -Algorithm SHA256).Hash) {
        throw "Non-deterministic image: $($file.Name)"
    }
}
```

验收已运行两个独立 Python 进程，七张 PNG 的 SHA256 全部一致；随后默认运行写入正式路径并与隔离输出比对。`run1.json`、`run2.json`、`determinism.json`、`runtime.json` 与 `preview.png` 留在上述 Temp QA 目录。已人工打开联系表和各单图，检查折叠粉条与螺旋卷粉的形态区分、洁净餐盒、纸箱比例，以及深浅背景和 64px 等效尺寸的可读性。这是离线贴图验收，不替代实际游戏加载检查。

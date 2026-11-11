# 壁挂全息招牌：顶视与旋转修复（2026-11-12）

## 本机引擎核查

直接用 `ilspycmd` 核查当前游戏 `Assembly-CSharp.dll`：

- `Placeworker_AttachedToWall.AllowsPlacing` 使用 `loc + GenAdj.CardinalDirections[rot.AsInt]`；四方向依次为北、东、南、西。建筑占用室内格，支撑墙在相邻格。
- 原版 `WallLamp` 的 `Graphic_Multi` offset 为北 `+0.9z`、东 `+0.9x`、南 `-0.9z`、西 `-0.9x`。这是透明画布中心的平移，不改变占格。
- `Graphic_Multi.Init` 四张 PNG 齐全时，四材质独立，`eastFlipped`/`westFlipped` 为 `false`，`extraAngle` 为 `0`。只有缺少方向贴图时才可能借用、镜像、追加角度。
- `Graphic.MatAt` 按 N/E/S/W 索引选择材质。`MeshAt` 的横向处理只是交换 `drawSize` 的两个分量（正方形无变化），不是旋转 UV；四方向独立时 `ShouldDrawRotated=false`，`QuatFromRot` 返回 `identity`。
- `Thing.Print → Graphic.Print` 打印底座；`MapMeshAndRealTime` 的已生成建筑不会在 `Thing.DrawAt` 再画一次底座，额外全息层由 comp 绘制。额外层使用引擎的 `QuatFromRot`。
- `MinifiedThing.DrawAt/Print` 使用内部建筑的底座 `Graphic`，抵消 `Graphic.DrawOffset` 后使用 `minifiedDrawOffset`；不会调用内部 comp 的 `PostDraw`。`IsIlluminated` 的 `Spawned`/`Map` 门槛另确保未生成的内部建筑不会投影。

## 根因与修复

旧生成器为南向重新写正立文字、东西向压缩并重新排版文字，西向还做左右镜像；这与「同一块画面刚性旋转」不同。

现在只生成一个北向顶视投影：原有完整菜单纵向压缩到 `0.16` 格，`0.0614` 格扇形连接发射槽；含边缘与局部光晕约 `0.23` 格。底座与全息层均通过无损 transpose 生成其余方向，东/南/西分别顺时针 `90°`/`180°`/`270°`，不重新排版、不镜像。墙面法线方向变换为 `R(x,z)=(z,-x)`，XML offsets 同样按此旋转。北向槽 `z=0.8414`，画面 `z=0.78..0.62`，投射方向朝室内。

XML 为壁挂两层显式设置 `drawRotated=false`、`allowFlip=false`，防止引擎二次旋转或镜像。底座四方向也统一旋转，避免沿用不一致的旧侧向发射槽。立式九张贴图与壁挂 UI 生成路径不变。

## 回归与验证

- `test_wall_rotation.py`：验证四方向两层逐像素刚性旋转以及实际 alpha 世界尺寸。
- `run-qa.ps1`：先跑像素回归，再 Release `-warnaserror` 构建与完整真实 DLL 离线 QA（**939 项 PASS**）。
- C# 新检查：实际原版四向附墙放置、材质索引、无镜像/无额外角、`identity` quaternion、未生成内部建筑不进入贴图解析；保留电力、太阳耀斑、订购和寻路检查。

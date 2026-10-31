# 食品级塑料：四族配方数值设计（待作者拍板）

日期：2026-10-31。目标环境：作者提供的 RimWorld 1.7.4990 rev1069（Waylith）；数据基准为本机 `/absolute/path/to/RimWorld/Data/Core/Defs/` 的 XML，未另行验证安装文件是否受过外部修改。

本次只交付设计文档，不生成或修改任何 mod 实现文件，不修改游戏目录。以下明确区分「原版实证」「作者固定规格」「设计提案」；新增配方数值都是从实证锚点推导的建议，不冒充原版已有数据。

## 0. 先纠正两处前提

1. **本机 Core 中高级零部件可制作**，并非原版不可制作：`RecipeDefs/Recipes_Production.xml:391-452` 有完整的 `Make_ComponentSpacer`，精密装配台明确挂载它（`ThingDefs_Buildings/Buildings_Production.xml:1251-1254`）。因此塑料方案定位为昂贵的替代材料路线，而非首次解锁原版不具备的能力。
2. **食品物品是 `MealSurvivalPack`**；`PackagedSurvivalMeal` 是研究 defName。分别见 `ThingDefs_Items/Items_Food.xml:55` 与 `ResearchProjectDefs/ResearchProjects_2_Electricity.xml:259`。

## 1. 作者固定规格（不可改动）

| 物品 | 每个质量 kg | 每个市场价值 银 | stackLimit |
|---|---:|---:|---:|
| PlasticGranule（粒） | 0.001 | 0.01 | 1500 |
| PlasticSheet（片） | 0.005 | 0.05 | 500 |

严格 `5 粒 = 1 片`，转换不损耗质量或名义市场价值。作者指定的外购惩罚基准为 0.5 银/个，本设计仅用 0.5 银/片检验合成成本，不验证或设计交易机制。

## 2. 原版实证摘录与出处

下列所有 `file:line` 均相对于上述 Core/Defs 根目录。质量单位 kg，价格单位银。定位使用 `rg -n`，随后逐段读取 XML。

### 2.1 原料与产物

| 对象 | XML 实证值 | file:line |
|---|---|---|
| Chemfuel | MarketValue 2.3；Mass 0.05；stackLimit 150 | `ThingDefs_Items/Items_Resource_Manufactured.xml:211,221,226-227` |
| Neutroamine | MarketValue 6；Mass 0.02；stackLimit 150 | `ThingDefs_Items/Items_Resource_Manufactured.xml:185,194,198-199` |
| Neutroamine description | `A synthetic precursor chemical. While it is useless on its own, many drugs require neutroamine as an ingredient.` | `ThingDefs_Items/Items_Resource_Manufactured.xml:187` |
| Steel | MarketValue 1.9；Mass 0.5 | `ThingDefs_Items/Items_Resource_Stuff.xml:135,145-146` |
| ComponentIndustrial | MarketValue 32；Mass 0.6；stackLimit 50 | `ThingDefs_Items/Items_Resource_Manufactured.xml:123,133,137-138` |
| ComponentSpacer | MarketValue 200；Mass 0.6；stackLimit 50 | `ThingDefs_Items/Items_Resource_Manufactured.xml:153,162,166-167` |
| MealSurvivalPack | MarketValue 24；Mass 0.3；WorkToMake 450；Nutrition 0.9 | `ThingDefs_Items/Items_Food.xml:55,64-67` |
| MealSimple | MarketValue 15；WorkToMake 300；Nutrition 0.9 | `ThingDefs_Items/Items_Food.xml:125-136` |
| 精致餐基类 MealFineBase | MarketValue 20；WorkToMake 450；Nutrition 0.9 | `ThingDefs_Items/Items_Food.xml:146-150` |
| 奢侈餐基类 MealLavishBase | MarketValue 40；WorkToMake 800；Nutrition 1 | `ThingDefs_Items/Items_Food.xml:208-214` |

精致餐三种子类位于 `ThingDefs_Items/Items_Food.xml:161-205`；奢侈餐三种子类从 `:224`、`:238`、`:252` 开始，继承上述营养值。精致餐好心情字段见 `:153-154`，奢侈餐见 `:216-217`；生存餐只标为 MealSimple 偏好（`:69-75`）。

**中性胺获取方式的证据边界：** description 只解释用途，**没有说明获取方式**，不能把「只能交易获得」冒充其原文。额外 `rg -n -C 3 Neutroamine Core/Defs` 找到商人库存，例如 `TraderKindDefs/TraderKinds_Caravan_Outlander.xml:34-36` 的 `StockGenerator_SingleDef / Neutroamine / 70~160`，证明存在交易供应；在本次 Core/Defs 搜索中未发现生产它的 RecipeDef 或 recipeMaker。保守结论是「此安装 Core 中未发现中性胺生产配方，存在商人供应」，不推断全部 DLC、事件或其他 mod 的来源。这里仅记录既有原料获取证据，不新增交易设计。

### 2.2 精炼设备现有配方（完整原文见附录）

| 配方 | 原料 | 产物 | workAmount | 速度属性 | 技能要求 |
|---|---|---|---:|---|---|
| Make_ChemfuelFromWood | WoodLog 70 | Chemfuel 35 | 2000 | GeneralLaborSpeed | 无显式 skillRequirements；无显式 workSkill |
| Make_ChemfuelFromOrganics | 食品/植物物质合计 3.5 营养 | Chemfuel 35 | 2500 | GeneralLaborSpeed | 无显式 skillRequirements；无显式 workSkill |

出处：`RecipeDefs/Recipes_Production.xml:268-295`、`:297-354`。有机物配方使用 `IngredientValueGetter_Nutrition`（`:307`），因此 `count=3.5`（`:324`）不是 3.5 个物品；允许混料，排除已制成的 FoodMeals、Hay、Dye 等，详见完整原文。

建筑挂配方与研究见 `ThingDefs_Buildings/Buildings_Production.xml:1174-1177,1211-1213`；研究 `BiofuelRefining` 定义在 `ResearchProjectDefs/ResearchProjects_2_Electricity.xml:54-62`，其前置为 Electricity。

### 2.3 原版生存食品配方与营养换算

`RecipeDefs/Recipes_Meals.xml:485-523`：

- `CookMealSurvival` 使用营养计量（`:494`）。
- 蛋白质原料（MeatRaw 或 AnimalProductRaw）0.30 营养（`:495-505`）。
- PlantFoodRaw 0.30 营养（`:506-513`）。
- 产出 MealSurvivalPack 1（`:515-517`），Cooking 8（`:518-520`），研究 PackagedSurvivalMeal（`:521`）。
- 输入总营养 0.60，产出营养 0.90（物品定义见 §2.1），即产出/投入 = **1.5 倍**。description 虽说 preservation 存在浪费，但实际配方并非营养减少，不能据文案改写这个算式。
- 单份 RecipeDef 未显式写 workAmount；成品 WorkToMake 为 450。下文以该 XML 制作工量锚点比较单份，实际运行时回退机制未另行反编译验证。
- x4 配方 `:525-564`：蛋白质 1.20 + 植物 1.20 营养 → 4 份，显式 workAmount 1440（`:530`），技能和研究不变（`:559-562`）。

原版简餐配方是 0.5 营养原料 → 1 份简餐（`RecipeDefs/Recipes_Meals.xml:32-58`），成品营养 0.9。封装路线不再重复烹饪增益：0.9 已烹饪营养只能得到 0.9 生存食品营养。

### 2.4 批量惯例：不是统一折扣

计算定义：`批量 workAmount ÷ (单份制作工量 × 份数)`；单份取对应物品 WorkToMake，批量取显式 RecipeDef。

| 原版餐食 | 单份工量锚点 | x4 工量 | 系数 | file:line |
|---|---:|---:|---:|---|
| 简餐 | 300 | 1200 | 1.00（无工量折扣） | `ThingDefs_Items/Items_Food.xml:135`；`RecipeDefs/Recipes_Meals.xml:65` |
| 精致餐 | 450 | 1800 | 1.00（无工量折扣） | `ThingDefs_Items/Items_Food.xml:149`；`RecipeDefs/Recipes_Meals.xml:189` |
| 奢侈餐 | 800 | 3200 | 1.00（无工量折扣） | `ThingDefs_Items/Items_Food.xml:212`；`RecipeDefs/Recipes_Meals.xml:386` |
| 生存餐 | 450 | 1440 | 0.80（工量八折） | `ThingDefs_Items/Items_Food.xml:66`；`RecipeDefs/Recipes_Meals.xml:530` |

**不能宣称原版所有 x4 都是八折，也不能宣称精致餐八折。** 本设计选择借用生存餐的 0.80，而非不存在的统一精炼折扣。

本机 `RecipeDefs/Recipes_Production.xml:268-354` 只有上述两种固定一批 35 燃料的配方，没有与之配对的 x4 版本，无法实证其「批量相对单份折扣」。`RecipeDefs/Recipes_Butchery.xml:4-52` 为单具尸体（count 1，workAmount 450），机械族拆解 `:54-110` 同样 count 1（workAmount 300 或 450），没有成对批量版。**精炼/屠宰批量折扣：未证实，不编造。**

### 2.5 零部件制造与研究

| 项目 | 原版实证 | file:line |
|---|---|---|
| 普通零部件 | Steel 12 → ComponentIndustrial 1；workAmount 5000；Crafting 8；workSkill Crafting；速度 GeneralLaborSpeed | `RecipeDefs/Recipes_Production.xml:356-389` |
| 普通零部件研究 | RecipeDef 无显式研究；FabricationBench 建筑要求 Fabrication | 同上；`ThingDefs_Buildings/Buildings_Production.xml:1290-1292` |
| 高级零部件 | ComponentIndustrial 1 + Steel 20 + Plasteel 10 + Gold **0.3（XML 原值）** → ComponentSpacer 1；workAmount 10000；Crafting 8；AdvancedFabrication；速度 GeneralLaborSpeed | `RecipeDefs/Recipes_Production.xml:391-452`，数量分别 `:408,:416,:424,:432` |
| 两种配方使用精密装配台 | 建筑 recipes 包含 Make_ComponentIndustrial、Make_ComponentSpacer | `ThingDefs_Buildings/Buildings_Production.xml:1251-1254` |
| Fabrication 研究 | 建造精密装配台，前置 MultiAnalyzer | `ResearchProjectDefs/ResearchProjects_4_MultiAnalyzer.xml:63-75` |
| AdvancedFabrication 研究 | 制作高级零部件，前置 Fabrication | `ResearchProjectDefs/ResearchProjects_4_MultiAnalyzer.xml:95-107` |

Gold 的小体积计量/运行时取整未验证，因此本稿不把 XML 的 0.3 擅自换成某个整数个数，也不据此核算高级零部件原版总材料价。普通零部件不存在此歧义：钢材市值成本 `12 × 1.9 = 22.8` 银，钢材质量 `12 × 0.5 = 6` kg，成品 32 银、0.6 kg。

## 3. 推荐数值方案总表

**以下全部为新增设计建议，不是原版事实。** 配方计量均为整数物品数量，食品另标营养。W 为显式 workAmount，不直接换算游戏小时；实际速度受工作属性、角色与设施影响。

研究缩写：B = BiofuelRefining；P = PackagedSurvivalMeal；F = Fabrication；A = AdvancedFabrication。表内「无（0）」表示不设最低技能等级，不表示不存在工作速度影响。

| ID / 配方 | 原料 | 产物 | W | 最低技能 | 研究 | 设备 | 一句话意图 |
|---|---|---|---:|---|---|---|---|
| S1 合成塑料粒 | Chemfuel 5 + Neutroamine 1 | 塑料粒 1500 | 2000 | 无（0） | B | BiofuelRefinery | 一次满粒堆，工量锚定原版木材炼油。 |
| S1b 合成塑料粒 x4 | Chemfuel 20 + Neutroamine 4 | 塑料粒 6000 | 6400 | 无（0） | B | BiofuelRefinery | 4 倍材料、4 倍产出，生存餐式八折工量。 |
| S2 合成塑料片 | Chemfuel 5 + Neutroamine 1 | 塑料片 300 | 2500 | 无（0） | B | BiofuelRefinery | 同等物料价值，加 500 成型工量。 |
| S2b 合成塑料片 x4 | Chemfuel 20 + Neutroamine 4 | 塑料片 1200 | 8000 | 无（0） | B | BiofuelRefinery | 直接产片，避免强制粒片两道工序。 |
| C1 压片 | 塑料粒 1500 | 塑料片 300 | 500 | 无（0） | B | BiofuelRefinery | 满粒堆转换，严格 5:1，无损。 |
| C2 造粒 | 塑料片 300 | 塑料粒 1500 | 500 | 无（0） | B | BiofuelRefinery | 与压片对称，无收益循环。 |
| P1 封装标准熟食 | 0.9 营养熟食（见白名单）+ 塑料片 12 | MealSurvivalPack 1（0.9 营养） | 150 | Cooking 8 | P | 电灶/燃料灶 | 补足简餐至生存餐的 150 工量差，不二次增营养。 |
| P1b 封装标准熟食 x4 | 3.6 营养熟食 + 塑料片 48 | MealSurvivalPack 4（3.6 营养） | 480 | Cooking 8 | P | 电灶/燃料灶 | 四份严格营养守恒，封装工量八折。 |
| P2 封装奢侈熟食（十份产出） | 奢侈餐 9（9 营养）+ 塑料片 120 | MealSurvivalPack 10（9 营养） | 1500 | Cooking 8 | P | 电灶/燃料灶 | 用 9→10 整数映射保住每份 1 营养的奢侈餐，不吞掉零头。 |
| P2b 封装奢侈熟食 x4 | 奢侈餐 36（36 营养）+ 塑料片 480 | MealSurvivalPack 40（36 营养） | 4800 | Cooking 8 | P | 电灶/燃料灶 | 相对 P2 四批八折；适合主动选择的大批远征备餐。 |
| F1 塑料零部件 | 塑料片 350 | ComponentIndustrial 1 | 7500 | Crafting 8 | F | FabricationBench | 比钢制略省材料钱，装配工量增加 50%。 |
| F2 塑料高级零部件 | 塑料片 4000 | ComponentSpacer 1 | 30000 | Crafting 12 | A | FabricationBench | 吞掉八满堆片料，以高成本、高技能、三倍装配工量换材料替代。 |

S1/S2 对应原版炼油的 2000/2500 工量锚点（§2.2）；C1/C2 的 500 是两者工量之差；所有 x4 的 `W = 单批 W × 4 × 0.8`（§2.4）。F1 的 1.5 倍和 F2 的 3 倍工量、Crafting 12 是**平衡提案系数/门槛**，不是声称原版有这些塑料配方。

P2/P2b 是确保「已烹饪食品」覆盖原版奢侈餐且不损失营养的配套方案；若作者只要基础熟食，建议先不上这两条，而不是偷偷把 1 营养奢侈餐按 0.9 消耗。

## 4. 各族经济与实施边界（仍不写实现）

### 4.1 合成成本：比惩罚价低，但不廉价刷价值

一次 S1/S2 的原料市值 `5 × 2.3 + 1 × 6 = 17.5` 银（§2.1）。产出等价 300 片：

- 自制原料机会成本 `17.5 / 300 = 0.058333… 银/片`，或 `17.5 / 1500 = 0.011666… 银/粒`。
- 相对作者 0.5 银/片基准低 **88.33%**，约为其 **1/8.57**。这里不含人工、电力、原料运输，也不是实际交易报价。
- 每批塑料名义市场价值 `300 × 0.05 = 1500 × 0.01 = 15` 银，**低于**投入原料 17.5 银；不靠合成增殖原料市值。
- 仍消耗中性胺：原料价中其占 `6/17.5 = 34.29%`，供应不足会限制规模；这不是完全闭环原料自给，而是塑料生产环节本地化。
- 单批/批量材料比例完全一致，批量只省工，不额外省原料。

**重要质量权衡：合成不是质量守恒模型。** 原料实测质量 `5 × 0.05 + 1 × 0.02 = 0.27 kg`，产出塑料 1.5 kg。固定极低的塑料单位市值、仅燃料+中性胺两种输入、普通零件要略省钱三者结合，会迫使高产率。这里公开保留游戏化质量增长，不能用「不管化学路径」暗示作者已同意质量增长。

其不可兼得的量化证据：若强行按原料质量守恒，最便宜的 Chemfuel 也需 `2.3 / 0.05 = 46 银/kg`，Neutroamine 为 `6 / 0.02 = 300 银/kg`；塑料固定名义价值却只有 `0.05 / 0.005 = 10 银/kg`。而本方案普通零部件要投入 1.75 kg 塑料，质量守恒合成的燃料成本下界已达 `1.75 × 46 = 80.5` 银（尚未加中性胺），不可能再与 22.8 银钢材路线「略省钱」同时成立。因此**质量增长是首要待拍板点**；若作者否决，应改成昂贵应急替代路线，不能假装所有目标仍同时成立。

### 4.2 精炼互转

- 1500 粒 = 300 片 = 1.5 kg = 15 银，往返严格守恒。
- 500 W 是与直接片料配方一致的成型费用：S1 2000 + C1 500 = S2 2500。
- 往返损失只有人工，不产生物料或价值；无需损耗项、催化剂或副产物。
- 批量 S1b 输出 6000 粒必须分四个满堆；S2b 1200 片需至少三堆。多堆产出、搬运及配方计数表现需后续实测，不把它视为单堆可容纳。

### 4.3 灶台封装：营养守恒、包装占比与食物边界

推荐每 0.9 营养成品用 **12 片**，即 60 g 包材（固定单位框架）。

- 包材名义价值 `12 × 0.05 = 0.6` 银，为原版成品价值 24 银的 **2.5%**。
- 包材自制原料成本 `12 × 17.5/300 = 0.7` 银，为 24 银的 **2.92%**。
- 简餐→生存餐的名义价值差是 `24 − 15 = 9` 银（§2.1）；包材吃掉该差额的 **6.67%**（名义）或 **7.78%**（自制原料）。其余差额对应保存/旅行用途与加工，不声称原版有可拆解的包装价值公式。
- P1 150 W 源于生存餐 WorkToMake 450 减简餐 300（§2.1）；Cooking 8 与研究 P 保持原版生存餐门槛。选择较低包装价是因为熟食已经支付过烹饪原料与工时，封装不应重新收一遍烹饪费。
- 普通生存餐的营养增益只有 1.5 倍，而简餐原料到成品是 1.8 倍（0.9/0.5）；封装简餐会允许素食路线以及更高的原料营养利用率，**这是作者要求的熟食封装自然带来的增强**，并非调高包材数量就能消除。保留研究/技能门槛，待实机确认强度。

**白名单和整数规则：**

- P1/P1b：只允许 MealSimple、MealFine、MealFine_Veg、MealFine_Meat；这些原版熟食均每个 0.9 营养（§2.1）。分别精确吃 1/4 个，可在相同营养白名单内混合；不包含营养膏、原料、尸体、饲料、现有生存餐等。
- P2/P2b：只允许 MealLavish、MealLavish_Veg、MealLavish_Meat，分别精确吃 9/36 个；每个 1 营养。合计恰好对应 10/40 份生存餐，塑料随产出份数线性计量。
- 所以 P1 为 `x=0.9,y=12`；P1b 为 `x=3.6,y=48`；P2 为 `x=9,y=120`；P2b 为 `x=36,y=480`。没有营养放大或损失，也不要求消耗小数个餐。
- 不要直接把所有 FoodMeals 塞进一个营养配方：原料会按整数取用，1.0 营养奢侈餐可能超投；固定产物数量不会自动把多出的 0.1 退还。
- 不要把 `IngredientValueGetter_Nutrition` 未经验证地用于「熟食 + 无营养塑料」的整个配方；建议采用白名单等营养、按个数精确消耗的实现路径，混合计量/无营养原料的运行行为目前未证实。
- 食品批量 x4 不是新的四倍烹饪增益，必须严格测试输入/输出营养等式；其他 mod 增改食物 Nutrition 后不自动承诺兼容。
- 食材来源、肉类/素食标记和食物中毒状态应如何传递，未做引擎实证。后续必须验证，不能通过封装洗掉禁忌食材、污染或中毒；本稿不承诺普通 XML 会自动正确完成所有传递。
- 奢侈餐转成普通偏好的生存餐会丢失高级餐的好心情用途、也会损失名义价值，应明确提示并默认不选用奢侈餐订单。

设备仅电灶/燃料灶，不扩展到篝火；原版灶台挂生存餐配方的证据是 `ThingDefs_Buildings/Buildings_Production.xml:712-728,805-821`。不需要 B 研究才能使用已持有片料封装，只有本地产塑料才要求 B。

### 4.4 普通零部件：省一点材料，付更多工时

采用片料而非同时新增粒料版，塑料粒先通过 C1 转片，减少重复订单并给予压片配方实际用途。

| 比较项 | 原版钢材路线 | 塑料路线 F1 |
|---|---:|---:|
| 原料名义市值 | 12 × 1.9 = 22.8 银 | 350 × 0.05 = 17.5 银（低 23.25%） |
| 塑料自制原料机会成本 | 不适用 | 350 × 17.5/300 = 20.4167 银（较钢材低 10.45%） |
| 装配 W | 5000 | 7500（高 50%） |
| 投入质量 | 6 kg | 1.75 kg |
| 产出 | 1 零部件，32 银/0.6 kg | 相同原版物品 |
| 最低技能/研究 | Crafting 8 / 建筑间接要求 F | Crafting 8 / 配方明确要求 F |

经济比较以自制成本那一行为主要平衡指标，而不是只看很低的塑料标价。

包含直接制片的摊销工量，F1 额外需要 `350/300 × 2500 = 2916.67 W` 的普通合成工量，或 `350/1200 × 8000 = 2333.33 W` 的 x4 合成摊销。总计分别 **10416.67 / 9833.33 W**，尚未算燃料生产与搬运；因此「略省材料但更费工」不仅是末端配方表面差异。这是产能/资源替代，不是低价无限刷零件方案。

### 4.5 高级零部件：昂贵应急替代，不越研究阶段

- 塑料片 4000 = 20 kg = **8 个满堆**，名义市值 200 银，恰好等于成品市值 200 银（§2.1）。
- 自制原料机会成本 `4000 × 17.5/300 = 233.333…` 银，已经比成品名义价值高 **16.67%**，还没算人工。
- 末端 W 30000 = 原版 10000 的 **3 倍**；Crafting 12 是在原版 Crafting 8 上再加 **4 级**的提案。门槛明确为 Crafting，不混入尚未验证必要性的 Intellectual 双技能。
- 仍要求 AdvancedFabrication，不降低到 Fabrication，也不能解决原版装配台初建所需资源的所有瓶颈。
- 摊销制片工量：普通批 `4000/300 × 2500 = 33333.33 W`，或 x4 `4000/1200 × 8000 = 26666.67 W`；加末端后 **63333.33 / 56666.67 W**，尚未算上游炼油与搬运。可积累现货，但不是高效替代原版生产。
- 不给高级零件 x4 省工版，避免削弱「长工时」的设计身份。只用片料，粒料先互转。
- 多堆材料搬运及中断恢复需验证；本稿不擅自增加 UnfinishedThingDef 或任何实现文件。

## 5. 最需要作者拍板的三个点

1. **接受合成质量增长吗？** 推荐以游戏经济优先，允许 0.27 kg 原料产 1.5 kg 塑料；粒片互转仍严格守恒。若必须合成也守恒，就必须牺牲「普通零部件略省材料钱」或调整输入框架，不能两者兼得。这是当前最大未决项。
2. **封装覆盖范围和强度：** 推荐 y=12 片/0.9 营养、Cooking 8、150 W，先开放 0.9 营养熟食白名单；奢侈餐另用 9→10 精确配方。是否一起上线奢侈餐两条，以及是否接受封装简餐绕过原版生存餐荤素原料结构、提升原料营养利用率，需要作者决定。
3. **高级零部件替代路线到底应多贵？** 推荐 4000 片 / 30000 W / Crafting 12 / AdvancedFabrication；其真实材料成本约 233.33 银，连制片总工量约原版末端的 5.67～6.33 倍。这个刻意保守的稀缺材料替代强度是否过于惩罚，需要作者确认，不能基于「原版不可制作」这个已被证伪的前提放宽。

## 6. 后续落地验收清单（不在本次实施）

- 原版值与本机摘录一致，尤其不要把 Gold 0.3 擅自抄为其他单位。
- 合成两种形态、普通/x4 的物料比一致；x4 只改工量系数。
- 粒片连续往返，质量与名义价值不变。
- 多堆产出与超单堆材料订单可完成、可中断；Crafting/Cooking 技能门槛真实生效。
- 食品逐条验证总营养严格相等，白名单外食品不能进入；排除生存餐自我封装。
- 验证原食材标签、素食/禁忌与食品安全状态；未验证前不可宣称能安全保留。
- 验证研究门槛、设备以及批量订单目标计数；实际工作速度/时长另做实测，不把 W 当成小时。

## 附录 A：精炼设备两条现有完整 RecipeDef 原文

下文从本机 `RecipeDefs/Recipes_Production.xml:268-354` 按原行读取，只用于证据存档，不是 mod 实现。

```xml
  <RecipeDef>
    <defName>Make_ChemfuelFromWood</defName>
    <label>make chemfuel from wood</label>
    <description>Make a batch of chemfuel by extracting and condensing wood gas from logs.</description>
    <jobString>Refining chemfuel from wood.</jobString>
    <effectWorking>Cremate</effectWorking>
    <soundWorking>Recipe_Cremate</soundWorking>
    <workAmount>2000</workAmount>
    <workSpeedStat>GeneralLaborSpeed</workSpeedStat>
    <ingredients>
      <li>
        <filter>
          <thingDefs>
            <li>WoodLog</li>
          </thingDefs>
        </filter>
        <count>70</count>
      </li>
    </ingredients>
    <fixedIngredientFilter>
      <thingDefs>
        <li>WoodLog</li>
      </thingDefs>
    </fixedIngredientFilter>
    <products>
      <Chemfuel>35</Chemfuel>
    </products>
  </RecipeDef>

  <RecipeDef>
    <defName>Make_ChemfuelFromOrganics</defName>
    <label>make chemfuel from organics</label>
    <description>Make a batch of chemfuel by extracting biofuel from organic feedstocks.</description>
    <jobString>Refining chemfuel from organics.</jobString>
    <effectWorking>Cremate</effectWorking>
    <soundWorking>Recipe_Cremate</soundWorking>
    <workAmount>2500</workAmount>
    <workSpeedStat>GeneralLaborSpeed</workSpeedStat>
    <allowMixingIngredients>true</allowMixingIngredients>
    <ingredientValueGetterClass>IngredientValueGetter_Nutrition</ingredientValueGetterClass>
    <ingredients>
      <li>
        <filter>
          <customSummary>feedstock</customSummary>
          <categories>
            <li>Foods</li>
            <li>PlantMatter</li>
          </categories>
          <disallowedThingDefs>
            <li>Hay</li>
            <li>Dye</li>
          </disallowedThingDefs>
          <disallowedCategories>
            <li>FoodMeals</li>
          </disallowedCategories>
        </filter>
        <count>3.5</count>
      </li>
    </ingredients>
    <fixedIngredientFilter>
      <categories>
        <li>Foods</li>
        <li>PlantMatter</li>
      </categories>
      <disallowedThingDefs>
        <li>Hay</li>
        <li>Dye</li>
        <li MayRequire="Ludeon.RimWorld.Biotech">HemogenPack</li>
        <li MayRequire="Ludeon.RimWorld.Biotech">BabyFood</li>
      </disallowedThingDefs>
      <disallowedCategories>
        <li>FoodMeals</li>
      </disallowedCategories>
    </fixedIngredientFilter>
    <defaultIngredientFilter>
      <categories>
        <li>FoodRaw</li>
      </categories>
      <disallowedCategories>
        <li>MeatRaw</li>
        <li>AnimalProductRaw</li>
      </disallowedCategories>
    </defaultIngredientFilter>
    <products>
      <Chemfuel>35</Chemfuel>
    </products>
  </RecipeDef>
```


## V2 重算（2026-10-31）

### V2.0 版本效力与证据口径

**本章取代旧 §1、§3～§6 的数值与结论；旧文原样保留，仅供历史追溯。** 尤其废止 5:1、旧价格 0.01/0.05、旧封装 y=12、纯塑料片零件路线和旧的 0.5 银/片外购比较。旧 §2 中未被本章纠正的 XML 摘录仍可作为实证。没有修改任何 mod 或游戏文件。

- **作者框架：** 粒为每单位一小把 50 g，Mass=0.05、stackLimit=1000，满堆 50 kg；片为大片/卷，Mass=1.67、stackLimit=75，满堆 125.25 kg。约 0.125 m³ 的堆积体积是设计标尺，不是引擎按 Mass 自动计算出的占地。价格待功能反推，未获批准。
- **作者结构：** 普通零部件用粒＋少量钢；高级零部件用 1 普通零部件＋粒＋少于原版的钢/玻璃钢＋3 个实物黄金；食品只用片。保留燃料＋中性胺的合成输入。
- **设计提案：** 下文所有新增产量、用量、W、价格、成本目标区间均为可拍板的建议，不是原版数值。“自制要亏”在本章操作化为**塑料合成产物名义市值低于投入原料市值**，以及高级零部件替代路线材料成本高于成品市值；并不要求普通零部件亏料，否则与“略省材料”直接矛盾。
- **原版实证：** XML 路径仍相对 `/absolute/path/to/RimWorld/Data/Core/Defs/`。新增代码证据来自本机根目录 `/absolute/path/to/RimWorld/Assembly-CSharp.dll`，用 ilspycmd 11.1.0 定点反编译；不是用异版本 wiki 猜行为。DLL SHA256：`4E61D57205944C113631234BC55136A1A7C1679667B26008BEE5425BCFFA1463`。反编译证据路径前缀记为 **E/** = `/absolute/path/to/plastic-v2-evidence/`，下文代码 file:line 相对于此目录。它是临时证据缓存，不是 mod 实现，复查时可由同 DLL 重建。尚未进游戏实测，也不保证其他 mod 不会补丁修改这些默认行为。

### V2.1 黄金与小数 count：已实证，不再留悬案

| 实证问题 | 本机证据与结论 |
|---|---|
| 字段叫什么 | Gold 的 `<smallVolume>true</smallVolume>` 在 `ThingDefs_Items/Items_Resource_Stuff.xml:97`；其 defName 在 `:70`，每实物 MarketValue=10、Mass=0.008 在 `:82,84`。Gold 也有 stuffProps（`:104-129`）。 |
| 10 个为什么等于 1 | `E/Verse.ThingDef.cs:460-469`：`VolumePerUnit` 对 smallVolume 返回 `0.1f`，否则 `1f`。`E/RimWorld.IngredientValueGetter_Volume.cs:8-15` 对 IsStuff 使用此值，非 Stuff 返回 1；所以不能把“任意小体积标签”不加条件地等同于全部配方自动乘十。 |
| RecipeDef 默认如何计量 | `E/Verse.RecipeDef.cs:41` 默认 `IngredientValueGetter_Volume`；默认 Worker 的计数返回原始 count（`E/Verse.RecipeWorker.cs:57-60`）。原版高级零件配方没有另设计量器，Gold count=0.3（`RecipeDefs/Recipes_Production.xml:391-452`，尤其 `:426-432`）。 |
| 实物数量怎么计算 | `E/Verse.IngredientCount.cs:52-55`：`CeilToInt(count / ValuePerUnitOf(def))`。Gold 因此为 `ceil(0.3/0.1)=3` 个实物，不是 0.3 个、也不是 30 个。**新高级零件也应填 Gold count=0.3，而不是 3**；后者在默认计量下要 30 个黄金。小体积不是重量/价格乘十规则；本配方黄金价格仍是 `3×10=30` 银，质量 `3×0.008=0.024 kg`。 |
| 原料选取/消费有没有真正取整 | 不混料分支调用上述 CountRequiredOfFor（`E/RimWorld.WorkGiver_DoBill.cs:631-658`）；混料分支也 `CeilToInt(剩余需求/每物单位价值)`（`:690-708`）。选定份数以整数拆堆（`E/Verse.AI.Toils_Recipe.cs:319`），完成后调用消费（`:370-374`），默认 Worker 销毁被选中的原料实体（`E/Verse.RecipeWorker.cs:44-47`）。没有“用半个、退半个”的机制。 |
| 普通粒/片能写小数吗 | **原料字段能存小数，但不能消耗小数实物。** `E/Verse.IngredientCount.cs:12` 的 count 是 float；对默认每单位值=1 的普通粒/片，0.5→1、1.2→2、33.4→34。此结论是已实证的默认配方路径，不是“XML 不支持小数”。特别的营养/自定义计量器另论，不能混为物品个数。 |
| 产物能是小数吗 | `E/Verse.ThingDefCountClass.cs:11` 的 count 是 int；`E/Verse.GenRecipe.cs:23` 在产物效率计算后仍把 stackCount 设为整数。普通 products 不能用 33.4 粒输出解决互转问题。 |
| 其他小体积物品 | 本机整个 `Data/` 的 `rg -n smallVolume` 只命中 Gold 与 Silver；Silver 在同 XML `:8,36`，每实物价值 1、质量 0.008 在 `:22-23`。结论限定为安装的 Data XML 显式声明，不涵盖 Mods、运行期生成或补丁新增的定义。 |

**由此补齐原版高级零部件经济锚点：** `1×32 + 20×1.9 + 10×9 + 3×10 = 190 银`；投入质量 `0.6 + 20×0.5 + 10×0.25 + 3×0.008 = 13.124 kg`，产物价值 200 银、质量 0.6 kg。零件/钢/成品出处见旧 §2.1、§2.5，新增玻璃钢价 9、质量 0.25 见 `ThingDefs_Items/Items_Resource_Stuff.xml:191,203-204`。因此原版自身也不是工业配方质量守恒模型；但这不等于作者已批准合成凭空增重。

### V2.2 先按 kg 锚定合成产量：三档一起比较

**原版实证输入锚：** 沿用 `Chemfuel 5 + Neutroamine 1`，机会成本 `5×2.3+6=17.5 银`、质量 `5×0.05+0.02=0.27 kg`（原料出处旧 §2.1）。以下产量都是提案，故不以“填满一堆”为由产出几十公斤。各档制片产量按“每 34 粒对应 1 片”匹配，制片略失重，具体见 V2.3。

| 产量档 | 单批粒：单位 / kg / 原料质量倍数 | 单批片：单位 / kg / 原料质量倍数 | 自制原料成本：银/粒；银/片 | 若采用下文固定候选价 0.24/8.016：粒批/片批名义市值 | 对定位的影响 |
|---|---|---|---|---|---|
| 保守 | 34 / 1.70 / 6.296× | 1 / 1.67 / 6.185× | 0.514706；17.50 | 8.16 / 8.016 | 合成明显亏市值；但下文普通零件材料变为 36.741 银，比原版 22.8 贵 61.15%，失去略省料身份。高级零件为 457.5 银，惩罚极重。 |
| **均衡（推荐）** | **68 / 3.40 / 12.593×** | **2 / 3.34 / 12.370×** | **0.257353；8.75** | **16.32 / 16.032** | 粒/片合成分别亏 1.18/1.468 银，即投入的 6.74%/8.39%，尚未算工电；普通零件 20.271 银，低 11.09%；高级零件 282.5 银。 |
| 激进 | 136 / 6.80 / 25.185× | 4 / 6.68 / 24.741× | 0.128676；4.375 | 32.64 / 32.064 | 固定候选价下合成反而增市值，违背“自制要亏”；普通零件 12.035 银（低 47.21%），高级零件 195 银（低于成品 200），三项定位一起变弱。 |

后三列普通零件均按 `64 粒＋2 钢`，高级均按 V2.5 的完整配方计价；这是单独改变产量时的敏感性比较，不是宣称保守/激进档也能直接套用均衡价格。激进若把粒价降到 `<0.128676` 才能保住合成亏损，普通零件名义材料价便 `<12.035 银`，仍不符合本章“略省料”的区间；若坚持该档就得连零件耗量一起重算。

**均衡档合成配方（提案）：** B=BiofuelRefining，设备均为 BiofuelRefinery；无最低技能，workSpeedStat 借用原版 GeneralLaborSpeed。W 不是游戏小时。

| 配方 | 输入 | 输出 | W | 输出质量 / 输入质量 |
|---|---|---|---:|---|
| V2-S1 合成粒 | 燃料 5＋中性胺 1 | 粒 68 | 2000 | 3.40 / 0.27 kg，12.593× |
| V2-S1b 合成粒 x4 | 燃料 20＋中性胺 4 | 粒 272 | 6400 | 13.60 / 1.08 kg，12.593× |
| V2-S2 合成片 | 燃料 5＋中性胺 1 | 片 2 | 2500 | 3.34 / 0.27 kg，12.370× |
| V2-S2b 合成片 x4 | 燃料 20＋中性胺 4 | 片 8 | 8000 | 13.36 / 1.08 kg，12.370× |

其他两档 x4 同样材料/单位数/kg 都乘四（保守 136 粒或 4 片；激进 544 粒或 16 片），W 仍为 6400/8000，只省工不省原料。2000/2500 的锚是原版两条炼油工量，x4 系数 0.8 借自原版生存餐而非炼油既有折扣，证据见旧 §2.2、§2.4。均衡 x4 输出均不超过新 stackLimit，但片堆 125.25 kg 的搬运仍需另测，不能把堆叠上限当单人运载保证。

**质量增长不能藏掉：** 均衡原料 0.27 kg→粒 3.4 kg，绝对净增 3.13 kg，比旧稿 1.5 kg 产量更激进。若严格守恒，燃料单位质量成本下界仍为 46 银/kg；单个普通零件的 3.2 kg 粒至少需 147.2 银的燃料，另加钢和中性胺，不能同时略低于原版 22.8 银。在固定两原料、不加未声明填充物/空气输入的范围内，必须由作者明确接受游戏化增重，或放弃普通零件略省料，不能靠改标价解决实耗成本。

旧 0.5 银/片是旧单位下的外购设定，本次价格未定，**不再声称自制比它便宜**。均衡自制片原料成本 8.75 银，高于候选 MarketValue 8.016，是“自制要亏”的直接体现；若作者仍想“自制显著低于外购惩罚价”，必须另给实际购入价格/溢价，不能用 MarketValue 冒充成交价，也不能擅自沿用 0.5。

### V2.3 粒↔片互转：整数小批、双向只损耗

**作者质量比：** `1.67/0.05 = 33.4 粒/片`。可选路径如下：

| 方案 | 压片 | 造粒 | 评价 |
|---|---|---|---|
| 对称 33:1 | 33 粒 1.65 kg→1 片 1.67 kg | 1 片→33 粒 | 压片凭空增加 20 g；不推荐。 |
| 对称 34:1 | 34 粒 1.70 kg→1 片 1.67 kg | 1 片→34 粒 | 造粒凭空增加 30 g；不推荐。 |
| **非对称整数（推荐）** | **34 粒→1 片，失 30 g/1.765%** | **1 片→33 粒，失 20 g/1.198%** | 双向都无物料增长；往返 34→33，损失 1 粒=50 g，即 2.941%。 |
| 精确整数大批 | 167 粒 8.35 kg→5 片 8.35 kg | 5 片→167 粒 | 33.4=167/5，**最小精确整数批是 167:5，不必等到 334:10**；严格守恒，但至少需要 5 片才可回收。可作为替代方案，不默认与有损小批同时上线。 |
| 小数 count | 33.4 粒→1 片 | 1 片→33.4 粒 | 前者实际向上取 34 粒，后者普通 products 不是 float；不能实现声称的无损 33.4:1。 |

推荐 C1/C2 各 W=250、B 研究、无最低技能、GeneralLaborSpeed、炼油设备。这样粒路线 `2000 W＋2×250 W` 恰好等于直接制 2 片的 2500 W，数量 68→2 也一致。造粒后不把损耗退回副产物；不另给 x4 互转折扣，避免绕路造粒取得较低合成工量。直接制片 17.5/2=8.75 银/片，反造粒自制成本 8.75/33=0.265152 银/粒，比直接制粒 0.257353 高，不能绕出廉价粒。

**名义价值无套利约束：** 若粒价 p、片价 s，则两方向不增值要求 `33p ≤ s ≤ 34p`。按质量建议 `s=33.4p`，与双向有损工艺兼容。精确大批方案若获选也恰好名义价值守恒，W 可用 1250/批（5 片×250）保持单位片工量；那时直接制片 2 片与压片最小批 5 片的订单粒度不再相同，要接受这点而非偷改合成产量。

### V2.4 封装：一片包 20 份，不再“每份 12 片”

**设计标尺，不冒充包装工程实测：** 原来 12×5 g=60 g/份；若暂时保留约 60 g 的旧平衡量，新片可包 `1.67/0.06≈27.83` 份，可取 28 份（59.64 g/份）。但 28 与奢侈餐 9→10 的营养整比难兼容。推荐折中取 **20 份/片，即每份 83.5 g**，而不是机械地把旧 y=12 延续成 20.04 kg 包一份饭。40 份/片=41.75 g 也是可选更薄包装；没有厚度/面积资料，不能声称哪档经物理工程验证。

20 份的优点是标准餐和奢侈餐都能用一片作为最小批量，营养严格守恒；缺点是取消真正单份封装，必须凑 20 份成品。按原版餐 0.3 kg 静态质量估算，83.5 g 包材相当于其 27.83%，并不很轻巧；输出仍为原版固定质量物品，这里不宣称成品物理质量守恒。

| 配方（提案） | 实物输入与营养 | 片数 y | 输出 | W | 技能/研究/设备 |
|---|---|---:|---|---:|---|
| V2-P1 标准封装（20 份批） | 标准熟食 20，18 营养 | 1 | 生存餐 20，18 营养 | 3000 | Cooking 8 / PackagedSurvivalMeal / 电灶或燃料灶 |
| V2-P1b 上述 x4 | 标准熟食 80，72 营养 | 4 | 生存餐 80，72 营养 | 9600 | 同上 |
| V2-P2 奢侈封装（可选，20 份批） | 奢侈餐 18，18 营养 | 1 | 生存餐 20，18 营养 | 3000 | 同上 |
| V2-P2b 上述 x4 | 奢侈餐 72，72 营养 | 4 | 生存餐 80，72 营养 | 9600 | 同上 |

标准白名单沿用 MealSimple、MealFine、MealFine_Veg、MealFine_Meat（每个 0.9 营养），奢侈白名单沿用 MealLavish、MealLavish_Veg、MealLavish_Meat（每个 1）；每份生存餐 0.9 的出处均见旧 §2.1、§2.3。建议按**实物个数**写配方，把营养作为校验等式，而不是把含无营养片料的整个 RecipeDef 改成营养计量。标准批的 `x=18 营养、y=1 片`，不是要在默认个数 count 中给熟食写 18（那会少吃两份）。同一白名单混料须显式选择/测试混料行为；不改用 FoodMeals 全类来省事。

W 保留旧稿每成品 150 的设计锚（450−300，出处旧 §2.1），20 份为 3000；x4 为 `3000×4×0.8=9600`。这里没有再把 20 份基础批额外八折，避免双重折扣。x4 是 **80 份**，不是 4 份；多堆输入输出、订单目标计数需测。

- 均衡候选价下：每成品包材名义值 `8.016/20=0.4008 银`，占生存餐 24 银的 **1.67%**；包材自制原料成本 `8.75/20=0.4375 银`，占 **1.823%**。对简餐转生存餐的 9 银名义价差，分别占 4.45%/4.86%。不重复收取整份饭的烹饪成本。
- `0.5 片` 或 `1/20 片` 不会真的扣半片/二十分之一片，只会扣 1 片；因此没有基于原版默认 count 的真正单份/四份便宜封装方案。若坚持小批，要另行批准可切分子物品或自定义余料机制，这超出本次纯设计范围，不能擅改片为 smallVolume。
- 28 份选项若覆盖奢侈餐且坚持 28 份/片，需最小公共产出 140 份（126 奢侈餐＋5 片）；这比推荐的 18＋1→20 大很多，是本次选 20 的实际理由。
- 营养守恒不等于无功能增强：简餐封装仍绕过原版生存餐荤素结构，并保留简餐 1.8 倍的原料营养收益，见旧 §4.3。奢侈餐好心情损失、食材/中毒/污染传递均仍待验证；本次没有证明普通 XML 会正确保留它们。建议先上标准白名单，奢侈配方待批准。

### V2.5 零部件：粒＋结构金属，明确数值与全链成本

| 配方（提案） | 输入（均为实物数量） | 输出 | W / 最低技能 | 研究 / 设备 |
|---|---|---|---|---|
| **V2-F1 普通零部件** | **粒 64＋钢 2** | 普通零部件 1 | **7500 / Crafting 8** | Fabrication / FabricationBench |
| **V2-F2 高级零部件** | **普通零部件 1＋粒 680＋玻璃钢 4＋钢 5＋黄金 3** | 高级零部件 1 | **30000 / Crafting 12** | AdvancedFabrication / FabricationBench |

两者 workSkill=Crafting、速度 GeneralLaborSpeed；研究、设备与原版锚点沿用旧 §2.5，7500/30000 和技能 12 是设计加价而非原版要求。**F2 的 XML Gold count 必须为 0.3**，表中 3 是作者指定的实物数。不给 F2 x4 省工版。

**普通零件的“少量钢”就是 2，较原版 12 少 83.33%。** 粒 64=3.2 kg，钢 2=1 kg，合计 4.2 kg→0.6 kg；这是工业加工抽象，不要求零件带着 4.2 kg 重量。候选粒价 p=0.24 时，名义材料 `64×0.24+2×1.9=19.16 银`，比原版 22.8 少 **15.96%**；均衡自制粒机会成本则为 `64×17.5/68+3.8=20.270588 银`，少 **11.09%**。两种口径都略省，不能只挑名义标价更好看的那行。

装配工量由 5000 增至 7500（+50%）；再加上游粒合成，普通批 `7500+64/68×2000=9382.35 W`，x4 摊销 `7500+64/272×6400=9005.88 W`，分别为原版末端的 1.876/1.801 倍。未计燃料制造、运输、电力与中性胺获取；不能把 W 当固定游戏小时或全部人工成本。

**高级零件不是廉价去金属路线：** 钢 5 对原版 20 少 75%，玻璃钢 4 对原版 10 少 60%，保留 1 普通零部件、3 黄金不变；用 680 粒=34 kg 来支付稀缺结构金属替代的惩罚。输入总质量 `0.6+34+4×0.25+5×0.5+3×0.008=38.124 kg`，产物仍 0.6 kg，粒未超过新满堆 1000 的上限；“大量消耗”是相对普通零件的 **10.625 倍粒**，不是沿用旧稿“八满堆”的说法。

| 高级零件比较 | 原版 | V2-F2（普通零件按市场机会成本 32 计） |
|---|---:|---:|
| 非塑料材料价 | 190 银（全部材料） | `32+4×9+5×1.9+3×10=107.5 银` |
| 塑料名义材料价 | 无 | `680×0.24=163.2 银` |
| 合计名义材料 | 190 银 | **270.7 银**，比原版高 42.47%，比成品 200 高 35.35% |
| 用均衡自制粒的真实上游原料价 | 不适用 | `107.5+680×17.5/68=282.5 银`，比原版高 48.68%，比成品高 41.25% |
| 末端工量 | 10000 W | 30000 W |
| 加粒合成摊销，普通/x4 | — | `30000+20000=50000` / `30000+16000=46000 W` |

若那 1 普通零件也沿 V2-F1 自制，展开其原料而非重复按 32 计：总原料 `282.5−32+20.270588=270.770588 银`，依然高于成品 200 **35.39%**；完整工量约 **59382.35 / 55005.88 W**（普通/粒 x4 摊销，不含钢/玻璃钢/黄金生产）。因此没有通过自制前级零件就把惩罚全部消掉。高级路线要求 AdvancedFabrication，不能用于跳过该研究阶段。

### V2.6 从功能反推建议 MarketValue，而非沿用旧价

**候选结论：粒 p=0.24 银/单位，片 s=8.016 银/单位。** 价格尚未拍板；片可在展示上约为 8.02，若实现时也四舍五入到 8.02，则须承认只是近似等单位质量价格（仍处于下述无套利区间）。推导顺序如下：

1. **先由质量定互转关系，不先定银价：** 要双向不增名义值，`33p≤s≤34p`；选质量等价 `s=33.4p`。这保证两者都是 `p/0.05=s/1.67` 银/kg，不给某种形态凭空贴溢价。
2. **普通零件要“略省”，先定义可核验目标：** 本章提议名义材料比原版 22.8 低 **10%～20%**，故 `18.24≤64p+3.8≤20.52`，得到 **`0.225625≤p≤0.26125`**。这是设计目标区间，不是作者已指定的百分比。
3. **塑料合成必须亏原料市值：** 均衡粒合成要 `68p<17.5`，即 **`p<0.257353`**；片要 `2s<17.5`，结合质量价约束得到 `p<8.75/33.4≈0.261976`。粒条件更紧。两者共同把可行粒价压至 **`0.225625≤p<0.257353`**。
4. **高级零件材料必须惩罚级：** 以原版价 190、成品价 200 为锚，提议名义材料至少 250 银（比成品高 25%），需要 `107.5+680p≥250`，即 `p≥0.209559`，不挤掉上一步区间；所以高级价格目标与普通省料可以同时成立，靠的是 680 对 64 的用量分级，而非为高级另造虚高标价。
5. **包材占比不能失控：** 提议名义包材为 24 银成品的 1%～3%，20 份/片要求 `0.24≤s/20≤0.72`，即 `4.8≤s≤14.4`。粒可行价换算片价约为 **7.536～8.5956 银**，完整落在包装允许区间；与高级惩罚并不冲突。
6. **在交集中取易读粒价 p=0.24：** 得 s=8.016，均为 **4.8 银/kg**。合成亏 6.74%/8.39%，普通名义省 15.96%/自制原料省 11.09%，高级名义材料 270.7 银/自制粒机会成本 282.5 银，包装每份名义 0.4008 银/自制原料 0.4375 银。所有目标同一组数下同时核验，而不是每项换一套价格。

由此新满堆名义值是粒 `1000×0.24=240 银`，片 `75×8.016=601.2 银`；满堆质量不同，满堆价值不必相等。MarketValue 是机会成本比较标尺，不是保证玩家能按它原价买卖；本章不设计交易供应/价格补丁，也不把出售税、电费或劳动折现暗藏进材料成本。

### V2.7 待作者拍板点与旧三点的变化

1. **合成质量增长仍是第一道门，并且增长更大。** 推荐均衡档 0.27 kg→68 粒/3.40 kg 或 2 片/3.34 kg，W 2000/2500；x4 只省工。旧稿 1.5 kg 与新单位不兼容已废止。若不接受约 12.4～12.6 倍增重，必须重新选定位/原料结构，不能声称守恒且普通仍省料。保守/激进的冲突见 V2.2。
2. **互转是否接受小额损耗，还是坚持无损大批？** 推荐 34 粒→1 片、1 片→33 粒，各 250 W；若要求严格守恒，改 167 粒↔5 片，各 1250 W。黄金与普通小数消耗已查清，**不再是待验证机制问题**；0.5 片方案不可当默认能力承诺。
3. **封装批次与覆盖范围：** 推荐 1 片包 20 份、标准批 3000 W、x4 80 份 9600 W，先只上标准熟食白名单；是否同时开放奢侈餐 18→20、是否接受凑批和简餐路线的原料营养优势，仍需决定。它替代旧第二点 y=12，不是只把 y 改成小数。
4. **批准功能定价与新零件惩罚档。** 推荐粒 0.24/片 8.016，普通 64 粒＋2 钢/7500 W；高级 1 零件＋680 粒＋4 玻璃钢＋5 钢＋3 黄金/30000 W/Crafting 12。旧第三点“纯 4000 片高级零件”被作者材料分工推翻，现方案保留核心电子/金属投入，反而可以给出已实证的原版 190 银比较。若仍要自制低于特殊外购价，另定实际购入惩罚，不能复活旧 0.5 银/片。

### V2.8 后续实现验收（本次不实施）

- 验证实物黄金恰吃 3 个，Gold 原料 XML count=0.3；普通粒/片不标 smallVolume，不靠小数 count 假装切片。
- 核验均衡四条合成数量、质量/价格统计、x4 只省工；互转按获批方案验证连续往返，不增质量/名义价值。
- 封装每批精确营养相等；白名单外、原生存餐、营养膏等不可进入；多堆 80 份输出、混料、订单目标与中断恢复均需实测。
- 食材来源、禁忌/素食标签、中毒/污染传递保留旧稿验证要求；在实证前不保证封装不会洗掉状态。
- 普通/高级配方只能消耗粒，包装只能消耗片；核验钢/玻璃钢减少量、Crafting/Cooking 门槛、研究、设备及工作属性。
- 分别记录“现货按 MarketValue 的机会成本”与“完整自制原料＋上游 W”，避免把 0.24 银误当粒真实自制成本 0.257353 银；实际搬运 50/125.25 kg 满堆能力另测。

using System.Globalization;
using System.Reflection;
using System.Xml.Linq;
using AyameICCT;
using HarmonyLib;
using RimWorld;
using Verse;

internal static partial class Program
{
    private sealed class QaChangfenRoomStatWorker : RoomStatWorker
    {
        public override float GetScore(Room room) => 0f;
    }

    private sealed class QaChangfenStatWorker : StatWorker
    {
        public override float GetValueUnfinalized(StatRequest req, bool applyPostProcess = true) => 0f;
    }

    private const string ChangfenRoot = @"G:\dev\starcct\";
    private static readonly string[] ChangfenNames = { "AyameICCT_Changfen", "AyameICCT_ZhuChangfen" };
    private static readonly string[] ChangfenRecipeNames =
    {
        "AyameICCT_Make_Changfen", "AyameICCT_Make_Changfen_Bulk",
        "AyameICCT_Make_ZhuChangfen", "AyameICCT_Make_ZhuChangfen_Bulk"
    };
    private static readonly string[] StarchNames = { "RawPotatoes", "RawToxipotato", "RawCorn", "RawRice", "DMSE_Carbohydrate" };

    private static void TestChangfen()
    {
        EnsureChangfenStatDefs();
        var allDefinitions = LoadDefinitions();
        var itemDocument = XDocument.Load(ChangfenRoot + @"Defs\ThingDefs\AyameICCT_Items_Changfen.xml");
        var itemXml = itemDocument.Root!.Elements("ThingDef").ToDictionary(x => x.Element("defName")!.Value);
        Check(itemXml.Count == 2 && ChangfenNames.All(itemXml.ContainsKey), "exactly the two requested Changfen ThingDefs exist");
        var changfen = ReadChangfenItem(itemXml[ChangfenNames[0]], allDefinitions);
        var zhu = ReadChangfenItem(itemXml[ChangfenNames[1]], allDefinitions);
        var foods = new[] { changfen, zhu };
        TestChangfenItemXml(itemXml[ChangfenNames[0]], changfen, allDefinitions);
        TestChangfenItemXml(itemXml[ChangfenNames[1]], zhu, allDefinitions);

        ThingDef potato = ChangfenExistingOrRead(allDefinitions, "RawPotatoes");
        ThingDef toxipotato = ChangfenExistingOrRead(allDefinitions, "RawToxipotato");
        ThingDef corn = ChangfenExistingOrRead(allDefinitions, "RawCorn");
        ThingDef rice = ChangfenExistingOrRead(allDefinitions, "RawRice");
        ThingDef carbohydrate = DefDatabase<ThingDef>.GetNamedSilentFail("DMSE_Carbohydrate")
            ?? Food("DMSE_Carbohydrate", 0.5f, FoodTypeFlags.Processed, FoodPreferability.RawBad);
        carbohydrate.thingCategories = new List<ThingCategoryDef> { ThingCategoryDefOf.PlantFoodRaw };
        ResolveChangfenThingCategories();
        var starch = new[] { potato, toxipotato, corn, rice, carbohydrate };
        var recipes = ReadChangfenRecipes(foods);
        TestChangfenRecipeXml(recipes, starch, rice, carbohydrate, foods);
        TestChangfenEating(foods);
        TestChangfenPackaging(foods);
        TestChangfenVanillaIngredients(foods);
        TestChangfenCarbohydrateLoop(recipes, carbohydrate, foods);
        TestChangfenTraders(foods);
        TestChangfenLocalization(itemXml);
    }

    private static void EnsureChangfenStatDefs()
    {
        foreach (FieldInfo field in typeof(StatDefOf).GetFields(BindingFlags.Public | BindingFlags.Static)
            .Where(f => f.FieldType == typeof(StatDef) && f.GetValue(null) == null))
        {
            field.SetValue(null, new StatDef
            {
                defName = "QA_" + field.Name,
                defaultBaseValue = 0f,
                minValue = float.NegativeInfinity,
                maxValue = float.PositiveInfinity
            });
        }
    }

    private static ThingDef ChangfenExistingOrRead(List<XElement> all, string name)
    {
        return DefDatabase<ThingDef>.GetNamedSilentFail(name) ?? ReadFood(all, name);
    }

    private static void ResolveChangfenThingCategories()
    {
        var categories = DefDatabase<ThingCategoryDef>.AllDefs.ToArray();
        foreach (ThingCategoryDef category in categories)
        {
            category.childCategories.Clear();
            category.childThingDefs.Clear();
        }
        foreach (ThingCategoryDef category in categories)
        {
            if (category.parent != null) category.parent.childCategories.Add(category);
        }
        foreach (ThingDef thing in DefDatabase<ThingDef>.AllDefs)
        {
            if (thing.thingCategories == null) continue;
            foreach (ThingCategoryDef category in thing.thingCategories)
            {
                if (!category.childThingDefs.Contains(thing)) category.childThingDefs.Add(thing);
            }
        }
        foreach (ThingCategoryDef category in categories) category.ResolveReferences();
    }

    private static float ChangfenFloat(XElement parent, string name)
    {
        return float.Parse(parent.Element(name)!.Value, CultureInfo.InvariantCulture);
    }

    private static ThingDef ReadChangfenItem(XElement xml, List<XElement> allDefinitions)
    {
        string name = xml.Element("defName")!.Value;
        var def = Food(name, ChangfenFloat(xml.Element("statBases")!, "Nutrition"), FoodTypeFlags.Meal, FoodPreferability.MealSimple);
        def.label = xml.Element("label")!.Value;
        def.description = xml.Element("description")!.Value;
        def.useHitPoints = true;
        def.selectable = true;
        def.socialPropernessMatters = true;
        def.alwaysHaulable = true;
        def.drawGUIOverlay = true;
        def.drawerType = DrawerType.MapMeshOnly;
        def.altitudeLayer = AltitudeLayer.Item;
        def.pathCost = 14;
        def.resourceReadoutPriority = ResourceCountPriority.Last;
        def.stackLimit = int.Parse(xml.Element("stackLimit")!.Value, CultureInfo.InvariantCulture);
        def.tradeability = Enum.Parse<Tradeability>(xml.Element("tradeability")!.Value);
        def.tickerType = Enum.Parse<TickerType>(xml.Element("tickerType")!.Value);
        def.graphicData = new GraphicData
        {
            texPath = xml.Element("graphicData")!.Element("texPath")!.Value,
            graphicClass = typeof(Graphic_StackCount)
        };
        def.thingCategories = ResolveChangfenThingCategories(xml, allDefinitions);
        def.statBases = xml.Element("statBases")!.Elements().Select(stat => new StatModifier
        {
            stat = (StatDef)typeof(StatDefOf).GetField(stat.Name.LocalName, BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!,
            value = float.Parse(stat.Value, CultureInfo.InvariantCulture)
        }).ToList();
        def.ingestible.maxNumToIngestAtOnce = int.Parse(xml.Element("ingestible")!.Element("maxNumToIngestAtOnce")!.Value, CultureInfo.InvariantCulture);
        def.ingestible.optimalityOffsetHumanlikes = ChangfenFloat(xml.Element("ingestible")!, "optimalityOffsetHumanlikes");
        def.ingestible.optimalityOffsetFeedingAnimals = ChangfenFloat(xml.Element("ingestible")!, "optimalityOffsetFeedingAnimals");
        XElement rottable = xml.Element("comps")!.Elements("li").Single(x => (string?)x.Attribute("Class") == "CompProperties_Rottable");
        XElement ingredients = xml.Element("comps")!.Elements("li").Single(x => (string?)x.Attribute("Class") == "CompProperties_Ingredients");
        def.comps.Add(new CompProperties_Forbiddable());
        def.comps.Add(new CompProperties_FoodPoisonable());
        def.comps.Add(new CompProperties_MetalhorrorInfectible());
        def.comps.Add(new CompProperties_Rottable
        {
            daysToRotStart = ChangfenFloat(rottable, "daysToRotStart"),
            rotDestroys = bool.Parse(rottable.Element("rotDestroys")!.Value)
        });
        def.comps.Add(new CompProperties_Ingredients
        {
            splitTransferableFoodKind = bool.Parse(ingredients.Element("splitTransferableFoodKind")!.Value),
            noIngredientsFoodKind = Enum.Parse<FoodKind>(ingredients.Element("noIngredientsFoodKind")!.Value)
        });
        Check(def.ConfigErrors().ToArray().Length == 0, name + " actual ThingDef.ConfigErrors is clean: " + string.Join("; ", def.ConfigErrors()));
        Check(ChangfenIntegration.IsChangfen(def), name + " uses the narrow production integration scope");
        return def;
    }

    private static List<XElement> ChangfenThingChain(XElement xml, List<XElement> allDefinitions)
    {
        var chain = new List<XElement> { xml };
        XElement current = xml;
        while ((string?)current.Attribute("ParentName") is string parent)
        {
            current = allDefinitions.Single(x => (string?)x.Attribute("Name") == parent);
            chain.Add(current);
        }
        return chain;
    }

    private static List<ThingCategoryDef> ResolveChangfenThingCategories(XElement xml, List<XElement> allDefinitions)
    {
        var inheritedNodes = new List<XElement>();
        foreach (XElement current in ChangfenThingChain(xml, allDefinitions))
        {
            XElement? categories = current.Element("thingCategories");
            if (categories == null) continue;
            inheritedNodes.Add(categories);
            if (string.Equals((string?)categories.Attribute("Inherit"), "False", StringComparison.OrdinalIgnoreCase)) break;
        }
        inheritedNodes.Reverse();
        return inheritedNodes.SelectMany(node => node.Elements("li"))
            .Select(node => DefDatabase<ThingCategoryDef>.GetNamed(node.Value)).ToList();
    }

    private static void TestChangfenItemXml(XElement xml, ThingDef def, List<XElement> allDefinitions)
    {
        string name = def.defName;
        bool plain = name == "AyameICCT_Changfen";
        var expectedStats = new Dictionary<string, float>
        {
            ["MaxHitPoints"] = 50f,
            ["Flammability"] = 1f,
            ["Beauty"] = 0f,
            ["Mass"] = plain ? 0.22f : 0.03f,
            ["MarketValue"] = plain ? 15f : 1.9f,
            ["Nutrition"] = plain ? 0.5f : 0.05f,
            ["WorkToMake"] = plain ? 300f : 420f,
            ["DeteriorationRate"] = 10f
        };
        foreach (var pair in expectedStats)
        {
            Check(Math.Abs(ChangfenFloat(xml.Element("statBases")!, pair.Key) - pair.Value) < 0.0001f
                && Math.Abs(def.GetStatValueAbstract((StatDef)typeof(StatDefOf).GetField(pair.Key)!.GetValue(null)!) - pair.Value) < 0.0001f,
                name + " XML and runtime stat " + pair.Key);
        }
        float fixedPoisonChance = def.GetStatValueAbstract(StatDefOf.FoodPoisonChanceFixedHuman);
        float simpleMealPoisonChance = DefDatabase<ThingDef>.GetNamed("MealSimple").GetStatValueAbstract(StatDefOf.FoodPoisonChanceFixedHuman);
        Check(xml.Element("statBases")!.Element("FoodPoisonChanceFixedHuman") == null
            && fixedPoisonChance == 0f && fixedPoisonChance == simpleMealPoisonChance,
            name + " has zero fixed food-poison chance like MealSimple, while retaining CompFoodPoisonable");
        Check(xml.Element("label")!.Value == (plain ? "plain rice noodle rolls" : "chee cheong fun"), name + " English fallback label");
        Check(xml.Element("graphicData")!.Element("texPath")!.Value == (plain ? "Things/Item/Meal/Changfen" : "Things/Item/Meal/ZhuChangfen")
            && xml.Element("graphicData")!.Element("graphicClass")!.Value == "Graphic_StackCount", name + " texture generator contract");
        Check(def.stackLimit == (plain ? 75 : 300) && def.tradeability == Tradeability.All && def.tickerType == TickerType.Rare, name + " stack, tradeability and ticker");
        Check(string.Equals((string?)xml.Element("thingCategories")!.Attribute("Inherit"), "False", StringComparison.OrdinalIgnoreCase)
            && xml.Element("thingCategories")!.Elements("li").Select(x => x.Value).SequenceEqual(new[] { "PlantFoodRaw" })
            && def.thingCategories.SequenceEqual(new[] { ThingCategoryDefOf.PlantFoodRaw })
            && def.FirstThingCategory == ThingCategoryDefOf.PlantFoodRaw
            && !def.IsWithinCategory(DefDatabase<ThingCategoryDef>.GetNamed("FoodMeals"))
            && def.IsWithinCategory(ThingCategoryDefOf.PlantFoodRaw)
            && def.IsWithinCategory(DefDatabase<ThingCategoryDef>.GetNamed("FoodRaw")),
            name + " resolves only PlantFoodRaw first for OgreStack RawFoodPlant, without FoodMeals inheritance");
        var ingest = xml.Element("ingestible")!;
        Check(def.ingestible.foodType == FoodTypeFlags.Meal && def.ingestible.preferability == FoodPreferability.MealSimple
            && ingest.Element("foodType")!.Value == "Meal" && ingest.Element("preferability")!.Value == "MealSimple", name + " simple-meal edibility");
        Check(ingest.Element("ingestEffect")!.Value == "EatVegetarian" && ingest.Element("ingestSound")!.Value == "Meal_Eat"
            && def.ingestible.optimalityOffsetHumanlikes == 16f && def.ingestible.optimalityOffsetFeedingAnimals == -25f,
            name + " vanilla simple-meal ingestion semantics");
        Check(def.ingestible.maxNumToIngestAtOnce == (plain ? 4 : 20), name + " multi-unit hunger ingestion cap");
        List<XElement> chain = ChangfenThingChain(xml, allDefinitions);
        Check(chain.All(x => x.Element("ingestible")?.Element("tasteThought") == null)
            && def.ingestible.tasteThought == null, name + " has no AteRawFood or any other direct taste thought");
        var comps = chain.SelectMany(x => x.Element("comps")?.Elements("li") ?? Enumerable.Empty<XElement>()).ToList();
        foreach (string comp in new[] { "CompProperties_Forbiddable", "CompProperties_FoodPoisonable", "CompProperties_MetalhorrorInfectible", "CompProperties_Rottable", "CompProperties_Ingredients" })
        {
            Check(comps.Count(x => (string?)x.Attribute("Class") == comp) == 1, name + " resolved comp " + comp);
        }
        var rot = comps.Single(x => (string?)x.Attribute("Class") == "CompProperties_Rottable");
        Check(ChangfenFloat(rot, "daysToRotStart") == 4f && bool.Parse(rot.Element("rotDestroys")!.Value)
            && def.GetCompProperties<CompProperties_Rottable>()!.daysToRotStart == 4f, name + " rots after four days like a simple meal");
        var ingredients = comps.Single(x => (string?)x.Attribute("Class") == "CompProperties_Ingredients");
        Check(bool.Parse(ingredients.Element("splitTransferableFoodKind")!.Value)
            && ingredients.Element("noIngredientsFoodKind")!.Value == "NonMeat", name + " ingredients component declares vegetarian fallback");
        Check(FoodUtility.GetFoodKind(def) == FoodKind.NonMeat && FoodUtility.GetFoodKind(MadeThing(def, 1)) == FoodKind.NonMeat,
            name + " actual FoodUtility def and empty-comp instance are NonMeat");
    }

    private static List<RecipeDef> ReadChangfenRecipes(ThingDef[] foods)
    {
        var result = new List<RecipeDef>();
        var root = XDocument.Load(ChangfenRoot + @"Defs\RecipeDefs\AyameICCT_Recipes_Changfen.xml").Root!;
        foreach (XElement xml in root.Elements("RecipeDef"))
        {
            XElement product = xml.Element("products")!.Elements().Single();
            ThingDef productDef = foods.Single(def => def.defName == product.Name.LocalName);
            var recipe = new RecipeDef
            {
                defName = xml.Element("defName")!.Value,
                label = xml.Element("label")!.Value,
                description = xml.Element("description")!.Value,
                jobString = xml.Element("jobString")!.Value,
                workAmount = int.Parse(xml.Element("workAmount")!.Value, CultureInfo.InvariantCulture),
                allowMixingIngredients = bool.Parse(xml.Element("allowMixingIngredients")!.Value),
                fixedIngredientFilter = new ThingFilter(),
                defaultIngredientFilter = new ThingFilter(),
                products = new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(productDef, int.Parse(product.Value, CultureInfo.InvariantCulture))
                }
            };
            Field(typeof(RecipeDef), "ingredientValueGetterClass").SetValue(recipe, typeof(IngredientValueGetter_Nutrition));
            XElement xmlIngredient = xml.Element("ingredients")!.Elements("li").Single();
            var ingredient = new IngredientCount();
            ingredient.SetBaseCount(ChangfenFloat(xmlIngredient, "count"));
            ReadChangfenCoreFilter(xmlIngredient.Element("filter"), ingredient.filter);
            recipe.ingredients.Add(ingredient);
            ReadChangfenCoreFilter(xml.Element("fixedIngredientFilter"), recipe.fixedIngredientFilter);
            ReadChangfenCoreFilter(xml.Element("defaultIngredientFilter"), recipe.defaultIngredientFilter);
            DefDatabase<RecipeDef>.Add(recipe);
            result.Add(recipe);
        }
        return result;
    }

    private static void ReadChangfenCoreFilter(XElement? xml, ThingFilter filter)
    {
        foreach (XElement node in xml?.Element("thingDefs")?.Elements("li") ?? Enumerable.Empty<XElement>())
        {
            if (node.Attribute("MayRequire") == null)
            {
                filter.SetAllow(DefDatabase<ThingDef>.GetNamed(node.Value), true);
            }
        }
    }

    private static ThingFilter[] ChangfenFilters(RecipeDef recipe)
    {
        return new[] { recipe.ingredients[0].filter, recipe.fixedIngredientFilter, recipe.defaultIngredientFilter };
    }

    private static void TestChangfenRecipeXml(List<RecipeDef> recipes, ThingDef[] starch, ThingDef rice, ThingDef carbohydrate, ThingDef[] foods)
    {
        Check(recipes.Count == 4 && recipes.Select(r => r.defName).SequenceEqual(ChangfenRecipeNames), "exactly four ordered Changfen recipes");
        var root = XDocument.Load(ChangfenRoot + @"Defs\RecipeDefs\AyameICCT_Recipes_Changfen.xml").Root!;
        foreach (RecipeDef recipe in recipes)
        {
            XElement xml = root.Elements("RecipeDef").Single(x => x.Element("defName")!.Value == recipe.defName);
            bool bulk = recipe.defName.EndsWith("_Bulk", StringComparison.Ordinal);
            bool plain = recipe.defName.Contains("Make_Changfen", StringComparison.Ordinal);
            float nutrition = bulk ? 3f : 0.3f;
            int work = plain ? (bulk ? 3000 : 300) : (bulk ? 4200 : 420);
            int output = plain ? (bulk ? 10 : 1) : (bulk ? 100 : 10);
            Check(recipe.ingredients.Count == 1 && recipe.ingredients[0].GetBaseCount() == nutrition
                && recipe.workAmount == work && recipe.products.Single().count == output, recipe.defName + " nutrition, work and output");
            Check(recipe.products.Single().thingDef.defName == (plain ? "AyameICCT_Changfen" : "AyameICCT_ZhuChangfen"), recipe.defName + " correct product");
            Check(recipe.allowMixingIngredients && recipe.IngredientValueGetter is IngredientValueGetter_Nutrition
                && xml.Element("ingredientValueGetterClass")!.Value == "IngredientValueGetter_Nutrition", recipe.defName + " native nutrition getter and mixing");
            foreach (string field in new[] { "workSpeedStat", "workSkill", "effectWorking", "soundWorking", "requiredGiverWorkType" })
            {
                string expected = field switch
                {
                    "workSpeedStat" => "CookSpeed",
                    "workSkill" => "Cooking",
                    "effectWorking" => "Cook",
                    "soundWorking" => "Recipe_CookMeal",
                    _ => "Cooking"
                };
                Check(xml.Element(field)!.Value == expected, recipe.defName + " cooking field " + field);
            }
            Check(xml.Element("recipeUsers")!.Elements("li").Select(x => x.Value).SequenceEqual(new[] { "ElectricStove", "FueledStove" }), recipe.defName + " both stoves");
            foreach (XElement filter in new[] { xml.Element("ingredients")!.Element("li")!.Element("filter")!, xml.Element("fixedIngredientFilter")!, xml.Element("defaultIngredientFilter")! })
            {
                Check(filter.Element("categories") == null && filter.Element("thingDefs")!.Elements("li").Select(x => x.Value).SequenceEqual(StarchNames),
                    recipe.defName + " explicit five-starch whitelist, never PlantFoodRaw");
                Check(filter.Element("thingDefs")!.Elements("li").Single(x => x.Value == "RawToxipotato").Attribute("MayRequire")!.Value == "Ludeon.RimWorld.Biotech"
                    && filter.Element("thingDefs")!.Elements("li").Single(x => x.Value == "DMSE_Carbohydrate").Attribute("MayRequire")!.Value == "Aoba.DeadManSwitch.Expedition",
                    recipe.defName + " XML optional ingredient gates");
            }
            Check(ChangfenFilters(recipe).All(f => !f.Allows(starch[1]) && !f.Allows(carbohydrate)), recipe.defName + " simulated MayRequire loading starts without optional inputs");
            Check(ChangfenFilters(recipe).All(f => f.Allows(starch[0]) && f.Allows(starch[2]) && f.Allows(starch[3])), recipe.defName + " three core starch inputs load directly");
        }

        ChangfenIntegration.Apply();
        ChangfenIntegration.Apply();
        StatDefOf.FoodPoisonChance = new StatDef
        {
            defName = "FoodPoisonChance",
            workerClass = typeof(QaChangfenStatWorker),
            defaultBaseValue = 0f
        };
        RoomStatDef foodPoisonRoomStat = DefDatabase<RoomStatDef>.AllDefs.First();
        foodPoisonRoomStat.workerClass = typeof(QaChangfenRoomStatWorker);
        foodPoisonRoomStat.roomlessScore = 0f;
        RoomStatDefOf.FoodPoisonChance = foodPoisonRoomStat;
        foreach (RoomStatDef roomStat in DefDatabase<RoomStatDef>.AllDefs)
        {
            roomStat.workerClass ??= typeof(QaChangfenRoomStatWorker);
        }
        foreach (RecipeDef recipe in recipes)
        {
            Check(ChangfenFilters(recipe).All(f => f.AllowedThingDefs.ToHashSet().SetEquals(starch)), recipe.defName + " dynamic resolver adds exactly both optional defs on all three surfaces");
            foreach (ThingDef food in foods)
            {
                Check(ChangfenFilters(recipe).All(f => !f.Allows(food)), recipe.defName + " rejects recursive ingredient " + food.defName);
                Check(!Bill(recipe).IsFixedOrAllowedIngredient(Thing(food, 75)), recipe.defName + " bill rejects recursive ingredient " + food.defName);
                SelectChangfenIngredients(recipe, food, 75, false, "cannot make Changfen from " + food.defName);
            }
            int riceCount = recipe.ingredients[0].CountRequiredOfFor(rice, recipe);
            Check(riceCount == (recipe.ingredients[0].GetBaseCount() == 0.3f ? 6 : 60), recipe.defName + " exact rice nutrition count");
            SelectChangfenIngredients(recipe, rice, riceCount, true, "native exact-rice selection");
            SelectChangfenIngredients(recipe, rice, riceCount - 1, false, "native insufficient-rice rejection");
            int carbohydrateCount = recipe.ingredients[0].CountRequiredOfFor(carbohydrate, recipe);
            Check(carbohydrateCount == (recipe.ingredients[0].GetBaseCount() == 0.3f ? 1 : 6), recipe.defName + " DMS carbohydrate input count");
            SelectChangfenIngredients(recipe, carbohydrate, carbohydrateCount, true, "native DMS carbohydrate selection");
            var worker = MoodPawn();
            var product = GenRecipe.MakeRecipeProducts(recipe, worker, new List<Thing> { MadeThing(rice, riceCount) }, null, null).Single();
            Check(product.def == recipe.products[0].thingDef && product.stackCount == recipe.products[0].count
                && Ingredients(product).ingredients.SequenceEqual(new[] { rice }), recipe.defName + " real GenRecipe output and ingredient record");
        }

        foreach (RecipeDef recipe in recipes)
        {
            foreach (ThingDef optional in new[] { starch[1], carbohydrate })
            {
                foreach (ThingFilter filter in ChangfenFilters(recipe)) filter.SetAllow(optional, false);
            }
        }
        AccessTools.Method(typeof(PlayDataLoader), "ResetStaticDataPost").Invoke(null, null);
        Check(recipes.All(r => ChangfenFilters(r).All(f => f.Allows(starch[1]) && f.Allows(carbohydrate))),
            "real AfterDefsResolved hook restores optional ingredients after a definition reload");
    }

    private static void SelectChangfenIngredients(RecipeDef recipe, ThingDef input, int count, bool expected, string behavior)
    {
        var bill = Bill(recipe);
        var available = new[] { Thing(input, count) }
            .Where(t => bill.IsFixedOrAllowedIngredient(t) && recipe.ingredients.Any(i => i.filter.Allows(t))).ToList();
        var chosen = new List<ThingCount>();
        var method = typeof(WorkGiver_DoBill).GetMethod("TryFindBestBillIngredientsInSet_AllowMix", BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingMethodException("AllowMix");
        bool actual = (bool)method.Invoke(null, new object?[] { available, bill, chosen, IntVec3.Zero, null })!;
        Check(actual == expected, recipe.defName + " " + behavior);
        if (expected)
        {
            Check(chosen.Sum(x => x.Count * recipe.IngredientValueGetter.ValuePerUnitOf(x.Thing.def)) + 0.0001f >= recipe.ingredients[0].GetBaseCount(),
                recipe.defName + " native selector meets nutrition for " + input.defName);
        }
    }

    private static void TestChangfenEating(ThingDef[] foods)
    {
        foreach (ThingDef def in foods)
        {
            var eater = MoodPawn();
            var thing = MadeThing(def, 1);
            Check(FoodUtility.ThoughtsFromIngesting(eater, thing, def).Count == 0,
                def.defName + " real ingestion thought preview has no raw-food penalty");
            var hungry = QaWorker();
            hungry.needs.food = new Need_Food(hungry) { CurLevel = 0f };
            int actual = FoodUtility.WillIngestStackCountOf(hungry, def, def.GetStatValueAbstract(StatDefOf.Nutrition));
            int expected = def.defName == "AyameICCT_Changfen" ? 2 : 20;
            Check(actual == expected, def.defName + " hungry pawn ingests multiple units in one meal session");
        }
    }

    private static void TestChangfenPackaging(ThingDef[] foods)
    {
        PackagingSettings settings = AyameICCTMod.Settings;
        settings.AllowRepackaging = false;
        PackagingFoodFilter.Apply(settings);
        var packagingRecipes = DefDatabase<RecipeDef>.AllDefs.Where(r => r.defName.StartsWith("AyameICCT_Pack_Meal_", StringComparison.Ordinal)).ToArray();
        Check(packagingRecipes.Length == 3, "all three existing packaging recipes remain registered");
        foreach (ThingDef def in foods)
        {
            Check(PackagingFoodFilter.CanPack(def, settings), def.defName + " is a narrow prepared-food exception to FoodRaw packaging exclusion");
            Check(packagingRecipes.All(r => r.ingredients[1].filter.Allows(def) && r.fixedIngredientFilter.Allows(def) && r.defaultIngredientFilter.Allows(def)),
                def.defName + " is packable into survival meals on all three filter surfaces");
        }
    }

    private static void TestChangfenVanillaIngredients(ThingDef[] foods)
    {
        var files = new[]
        {
            Path.Combine(GameRoot, @"Data\Core\Defs\RecipeDefs\Recipes_Meals.xml"),
            Path.Combine(GameRoot, @"Data\Core\Defs\RecipeDefs\Recipes_Food.xml")
        };
        var recipes = files.SelectMany(file => XDocument.Load(file).Root!.Elements("RecipeDef")).ToList();
        foreach (string name in new[] { "CookMealSimple", "CookMealFine", "CookMealFine_Veg", "CookMealLavish", "Make_Pemmican", "CookMealSurvival" })
        {
            XElement xml = recipes.Single(x => x.Element("defName")?.Value == name);
            var filters = xml.Element("ingredients")!.Elements("li").Select(x => x.Element("filter")!).Select(filterXml =>
            {
                var filter = new ThingFilter();
                foreach (XElement category in filterXml.Element("categories")?.Elements("li") ?? Enumerable.Empty<XElement>())
                {
                    filter.SetAllow(DefDatabase<ThingCategoryDef>.GetNamed(category.Value), true);
                }
                return filter;
            }).ToArray();
            foreach (ThingDef food in foods)
            {
                Check(filters.Any(f => f.Allows(food)), name + " real ThingFilter accepts " + food.defName + " as a downstream ingredient");
            }
        }
    }

    private static ThingFilter ReadChangfenCategoryFilter(XElement? xml, ThingDef carbohydrate)
    {
        var filter = new ThingFilter();
        foreach (XElement category in xml?.Element("categories")?.Elements("li") ?? Enumerable.Empty<XElement>())
        {
            filter.SetAllow(DefDatabase<ThingCategoryDef>.GetNamed(category.Value), true);
        }
        foreach (XElement disallowed in xml?.Element("disallowedThingDefs")?.Elements("li") ?? Enumerable.Empty<XElement>())
        {
            if (disallowed.Value == "DMSE_Carbohydrate") filter.SetAllow(carbohydrate, false);
        }
        return filter;
    }

    private static void TestChangfenCarbohydrateLoop(List<RecipeDef> recipes, ThingDef carbohydrate, ThingDef[] foods)
    {
        const string path = @"A:\SteamLibrary\steamapps\workshop\content\294100\3689879335\1.7\Defs\RecipeDefs\DMSE_Recipe_CleanRoom.xml";
        XElement xml = XDocument.Load(path).Root!.Elements("RecipeDef").Single(x => x.Element("defName")?.Value == "DMSE_Make_Carbohydrate");
        var recipe = new RecipeDef
        {
            defName = "DMSE_Make_Carbohydrate",
            fixedIngredientFilter = new ThingFilter(),
            defaultIngredientFilter = new ThingFilter(),
            products = new List<ThingDefCountClass> { new ThingDefCountClass(carbohydrate, 2) }
        };
        Field(typeof(RecipeDef), "ingredientValueGetterClass").SetValue(recipe, typeof(IngredientValueGetter_Nutrition));
        XElement ingredientXml = xml.Element("ingredients")!.Elements("li").Single();
        var ingredient = new IngredientCount();
        ingredient.SetBaseCount(ChangfenFloat(ingredientXml, "count"));
        ingredient.filter = ReadChangfenCategoryFilter(ingredientXml.Element("filter"), carbohydrate);
        recipe.ingredients.Add(ingredient);
        recipe.fixedIngredientFilter = ReadChangfenCategoryFilter(xml.Element("fixedIngredientFilter"), carbohydrate);
        recipe.defaultIngredientFilter = ReadChangfenCategoryFilter(xml.Element("defaultIngredientFilter"), carbohydrate);
        Check(xml.Element("ingredientValueGetterClass")!.Value == "IngredientValueGetter_Nutrition"
            && xml.Element("products")!.Element("DMSE_Carbohydrate")!.Value == "2", "actual DME synthetic-starch recipe contract");
        foreach (ThingDef food in foods)
        {
            Check(ChangfenFilters(recipe).All(f => f.Allows(food)), "DMSE_Make_Carbohydrate accepts " + food.defName + " through PlantFoodRaw");
        }
        Check(recipe.ingredients[0].CountRequiredOfFor(foods[0], recipe) == 2
            && recipe.ingredients[0].CountRequiredOfFor(foods[1], recipe) == 20, "DMS extraction uses actual Changfen nutrition");
        Check(ChangfenFilters(recipe).All(f => !f.Allows(carbohydrate))
            && recipes.All(r => ChangfenFilters(r).All(f => f.Allows(carbohydrate))),
            "DMSE_Carbohydrate -> Changfen -> DMSE_Carbohydrate loop closes without direct carbohydrate self-input");
    }

    private static TraderKindDef ReadChangfenTrader(XElement xml, ThingDef survival, ThingDef[] foods)
    {
        var trader = new TraderKindDef { defName = xml.Element("defName")!.Value };
        foreach (XElement node in xml.Element("stockGenerators")!.Elements("li"))
        {
            string kind = node.Attribute("Class")!.Value;
            StockGenerator? generator = null;
            if (kind == "StockGenerator_BuyExpensiveSimple")
            {
                generator = new StockGenerator_BuyExpensiveSimple();
            }
            else if (kind == "StockGenerator_Category")
            {
                string category = node.Element("categoryDef")!.Value;
                if (category is "FoodRaw" or "FoodMeals" or "Foods")
                {
                    var categoryGenerator = new StockGenerator_Category();
                    Field(typeof(StockGenerator_Category), "categoryDef").SetValue(categoryGenerator, DefDatabase<ThingCategoryDef>.GetNamed(category));
                    var excluded = node.Element("excludedCategories")?.Elements("li")
                        .Select(x => DefDatabase<ThingCategoryDef>.GetNamedSilentFail(x.Value)).Where(x => x != null).ToList();
                    if (excluded != null) Field(typeof(StockGenerator_Category), "excludedCategories").SetValue(categoryGenerator, excluded);
                    generator = categoryGenerator;
                }
            }
            else if (kind == "StockGenerator_SingleDef")
            {
                ThingDef? target = node.Element("thingDef")!.Value == "MealSurvivalPack" ? survival : foods.FirstOrDefault(f => f.defName == node.Element("thingDef")!.Value);
                if (target != null)
                {
                    var single = new StockGenerator_SingleDef();
                    Field(typeof(StockGenerator_SingleDef), "thingDef").SetValue(single, target);
                    generator = single;
                }
            }
            else if (kind == "StockGenerator_MultiDef")
            {
                var targets = node.Element("thingDefs")!.Elements("li").Select(x => x.Value == "MealSurvivalPack" ? survival : foods.FirstOrDefault(f => f.defName == x.Value))
                    .Where(x => x != null).Cast<ThingDef>().ToList();
                if (targets.Count > 0)
                {
                    var multi = new StockGenerator_MultiDef();
                    Field(typeof(StockGenerator_MultiDef), "thingDefs").SetValue(multi, targets);
                    generator = multi;
                }
            }
            if (generator != null)
            {
                generator.ResolveReferences(trader);
                trader.stockGenerators.Add(generator);
            }
        }
        return trader;
    }

    private static void TestChangfenTraders(ThingDef[] foods)
    {
        InstallPatches();
        var expensive = AccessTools.Method(typeof(StockGenerator_BuyExpensiveSimple), nameof(StockGenerator_BuyExpensiveSimple.HandlesThingDef));
        Check(Harmony.GetPatchInfo(expensive).Postfixes.Count(p => p.owner == AyameICCTMod.PackageId) == 1,
            "BuyExpensiveSimple Changfen postfix installed exactly once");
        ThingDef survival = ThingDefOf.MealSurvivalPack;
        survival.tradeability = Tradeability.All;
        survival.BaseMarketValue = 24f;
        var generator = new StockGenerator_BuyExpensiveSimple();
        Check(foods[0].BaseMarketValue / foods[0].VolumePerUnit >= 15f && generator.HandlesThingDef(foods[0]),
            "plain Changfen naturally passes BuyExpensiveSimple");
        Check(foods[1].BaseMarketValue / foods[1].VolumePerUnit < 15f && generator.HandlesThingDef(foods[1]),
            "low-value chee cheong fun passes through the narrow Harmony postfix");
        Check(generator.TradeabilityFor(foods[0]) == Tradeability.Sellable && generator.TradeabilityFor(foods[1]) == Tradeability.Sellable,
            "BuyExpensiveSimple explicitly permits players to sell both Changfen foods");

        var roots = new[]
        {
            Path.Combine(GameRoot, @"Data\Core\Defs\TraderKindDefs"),
            Path.Combine(GameRoot, @"Data\Royalty\Defs\TraderKindDefs")
        };
        var traderXml = roots.SelectMany(root => Directory.EnumerateFiles(root, "*.xml", SearchOption.AllDirectories))
            .SelectMany(file => XDocument.Load(file).Root!.Elements("TraderKindDef")).ToList();
        var traders = traderXml.Select(x => ReadChangfenTrader(x, survival, foods)).ToList();
        int survivalTraders = traders.Count(t => t.WillTrade(survival));
        Check(traders.Count == 20 && survivalTraders > 0, "all 20 vanilla Core/Royalty trader kinds evaluated against survival-meal baseline");
        for (int i = 0; i < traders.Count; i++)
        {
            TraderKindDef trader = traders[i];
            bool baseline = trader.WillTrade(survival);
            bool hasExpensiveGenerator = traderXml[i].Element("stockGenerators")!.Elements("li").Any(x => x.Attribute("Class")?.Value == "StockGenerator_BuyExpensiveSimple");
            if (hasExpensiveGenerator) Check(baseline, trader.defName + " vanilla survival-meal trader control");
            foreach (ThingDef food in foods)
            {
                Check(trader.WillTrade(food) == baseline, trader.defName + " trader acceptance matches MealSurvivalPack for " + food.defName);
                if (baseline)
                {
                    var handling = trader.stockGenerators.Where(g => g.HandlesThingDef(food)).ToArray();
                    Check(handling.Length > 0 && handling.Any(g => g.TradeabilityFor(food) is Tradeability.Sellable or Tradeability.All),
                        trader.defName + " permits player selling " + food.defName);
                }
            }
        }
    }

    private static void TestChangfenLocalization(Dictionary<string, XElement> itemXml)
    {
        const string plainEnglish = "Preliminary drawer-style rice noodle rolls with no filling, no side dishes, and not even a soy sauce packet, commonly known as 'plain changfen'. Soft without sticking, loose without clumping, tender, smooth, and savory.\\nIt can be further cooked into other foods, or heated and eaten directly, though it tastes rather plain on its own.\\nIts origin in the cosmos is disputed, but rimworld locals independently figured out how to make it.\\nAs a refined carbohydrate processed food, it is also hard currency gladly bought by traders.";
        const string zhuEnglish = "Preliminary rolled rice noodles with no filling, side dishes, or sauce. The rice sheet is white as snow, thin as paper, and as tender and smooth as a young girl's skin.\\nIt can be further cooked into other foods, and pairs well with chili soy sauce or sweet sauces.\\nIt can also be heated and eaten directly, though it tastes rather plain on its own.\\nAs a refined carbohydrate processed food, it is also hard currency gladly bought by traders.";
        const string plainChinese = "初步加工的抽屉式肠粉，没有馅料，没有配菜，甚至没有豉油酱汁包，俗称「斋肠粉」。软而不黏、松而不板结，嫩滑鲜美。\\n它可以被进一步加工成其他食物，也可以热热直接吃，虽然这样味道一般。\\n它在宇宙中的起源众说纷纭，但边缘世界的本地人民自己探索出了它的制作方法。\\n作为一种精制碳水加工食品，它也是商人乐意收购的硬通货。";
        const string zhuChinese = "初步加工的猪肠粉，没有馅料、配菜和酱料。粉质白如雪、薄如纸、像少女肌肤一样嫩滑。\\n它可以被进一步加工成其他食物，蘸着辣椒豉油或者甜口的酱料都很适合。\\n它也可以热热直接吃，虽然这样味道一般。\\n作为一种精制碳水加工食品，它也是商人乐意收购的硬通货。";
        Check(itemXml[ChangfenNames[0]].Element("description")!.Value == plainEnglish && itemXml[ChangfenNames[1]].Element("description")!.Value == zhuEnglish,
            "ThingDef English fallback descriptions exactly match the draft translation");
        var recipeXml = XDocument.Load(ChangfenRoot + @"Defs\RecipeDefs\AyameICCT_Recipes_Changfen.xml").Root!.Elements("RecipeDef").ToDictionary(x => x.Element("defName")!.Value);
        var chineseLabels = new[] { "制作斋肠粉", "批量制作斋肠粉", "制作猪肠粉", "批量制作猪肠粉" };
        var englishLabels = new[] { "make plain rice noodle rolls", "make plain rice noodle rolls x10", "make chee cheong fun x10", "make chee cheong fun x100" };
        foreach (string language in new[] { "ChineseSimplified", "English" })
        {
            var things = XDocument.Load(ChangfenRoot + $@"Languages\{language}\DefInjected\ThingDef\AyameICCT_Items_Changfen.xml").Root!;
            var translatedRecipes = XDocument.Load(ChangfenRoot + $@"Languages\{language}\DefInjected\RecipeDef\AyameICCT_Recipes_Changfen.xml").Root!;
            string[] labels = language == "English" ? englishLabels : chineseLabels;
            Check(things.Element("AyameICCT_Changfen.label")!.Value == (language == "English" ? "plain rice noodle rolls" : "肠粉条")
                && things.Element("AyameICCT_ZhuChangfen.label")!.Value == (language == "English" ? "chee cheong fun" : "猪肠粉"), language + " exact Changfen item labels");
            Check(things.Element("AyameICCT_Changfen.description")!.Value == (language == "English" ? plainEnglish : plainChinese)
                && things.Element("AyameICCT_ZhuChangfen.description")!.Value == (language == "English" ? zhuEnglish : zhuChinese), language + " exact four-paragraph item descriptions");
            for (int i = 0; i < ChangfenRecipeNames.Length; i++)
            {
                string name = ChangfenRecipeNames[i];
                Check(translatedRecipes.Element(name + ".label")!.Value == labels[i]
                    && translatedRecipes.Element(name + ".description")!.Value == recipeXml[name].Element("description")!.Value == (language == "English"),
                    language + " recipe label and fallback description " + name);
                Check(!string.IsNullOrWhiteSpace(translatedRecipes.Element(name + ".jobString")!.Value)
                    && !string.IsNullOrWhiteSpace(translatedRecipes.Element(name + ".ingredients.0.filter.customSummary")!.Value),
                    language + " recipe job and starch summary " + name);
            }
        }
    }
}

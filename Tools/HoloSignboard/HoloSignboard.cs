using System.Reflection;
using System.Xml.Linq;
using AyameICCT;
using RimWorld;
using Verse;
using Verse.AI;

internal static partial class Program
{
    private sealed class QaSignFlare : GameCondition { public override bool ElectricityDisabled => true; }

    private static void TestHoloSignboard()
    {
        TestHoloSignboardVariant(false);
        TestHoloSignboardVariant(true);
    }

    private static void TestHoloSignboardVariant(bool wallMounted)
    {
        EnsureShopEnvironment();
        Faction.OfPlayer.ideos ??= new FactionIdeosTracker(Faction.OfPlayer);
        Find.World.ideoManager ??= new IdeoManager();
        const string root = @"G:\dev\starcct\";
        string defName = wallMounted ? "AyameICCT_WallHoloSignboard" : "AyameICCT_HoloSignboard";
        string texture = wallMounted ? "WallHoloSignboard" : "HoloSignboard";
        XElement xml = XDocument.Load(root + @"Defs\ThingDefs\AyameICCT_Buildings_HoloSignboard.xml").Root!.Elements("ThingDef").Single(x => x.Element("defName")!.Value == defName);
        Check(xml.Element("hasInteractionCell") == null && xml.Element("interactionCellOffset") == null, defName + " has no operation marker");
        Check(xml.Element("minifiedDef")!.Value == "MinifiedThing" && xml.Element("thingCategories")!.Elements("li").Any(), defName + " minification XML");
        foreach (var pair in new Dictionary<string, string>
        {
            ["defName"] = defName, ["size"] = wallMounted ? "(1, 1)" : "(2, 1)",
            ["designationCategory"] = "Misc", ["altitudeLayer"] = wallMounted ? "BuildingOnTop" : "Building",
            ["passability"] = wallMounted ? "Standable" : "PassThroughOnly", ["pathCost"] = wallMounted ? "0" : "50",
            ["rotatable"] = "true", ["drawerType"] = "MapMeshAndRealTime",
            ["thingClass"] = typeof(Building_HoloSignboard).FullName!,
            ["uiIconPath"] = $"Things/Building/{texture}/{texture}_UI"
        }) Check(xml.Element(pair.Key)?.Value == pair.Value, "sign XML " + pair.Key);
        foreach (var pair in new Dictionary<string, string>
        { ["MaxHitPoints"] = wallMounted ? "50" : "80", ["WorkToBuild"] = wallMounted ? "2500" : "4000", ["Flammability"] = "1.0", ["Mass"] = wallMounted ? "8" : "20" })
            Check(xml.Element("statBases")!.Element(pair.Key)!.Value == pair.Value, "sign stat " + pair.Key);
        Check(xml.Element("costList")!.Element("Steel")!.Value == (wallMounted ? "40" : "80")
            && xml.Element("costList")!.Element("ComponentIndustrial")!.Value == (wallMounted ? "1" : "2"), "sign materials");
        Check(xml.Element("researchPrerequisites")!.Element("li")!.Value == "MicroelectronicsBasics", "sign research");
        var comps = xml.Element("comps")!.Elements("li").ToList();
        Check(comps.Single(x => (string?)x.Attribute("Class") == "CompProperties_Power").Element("basePowerConsumption")!.Value == (wallMounted ? "100" : "200"), "sign wattage");
        Check(comps.Any(x => (string?)x.Attribute("Class") == "CompProperties_Flickable"), "sign flickable XML");
        Check(comps.Single(x => (string?)x.Attribute("Class") == "CompProperties_Glower").Element("glowColor")!.Value == "(10,255,10,1)", "sign bright green glow");
        var holoXml = comps.Single(x => (string?)x.Attribute("Class") == typeof(CompProperties_HoloSignboard).FullName).Element("graphicDataExtra")!;
        Check(holoXml.Element("shaderType")!.Value == "TransparentPostLight", "post-light hologram shader");
        Check(holoXml.Element("graphicClass")!.Value == "Graphic_Multi" && holoXml.Element("drawSize")!.Value == (wallMounted ? "(2.6, 2.6)" : "(3.8, 3.8)"), "four-direction hologram dimensions");
        Check(holoXml.Element("texPath")!.Value == $"Things/Building/{texture}/{texture}Hologram", "hologram path contract");
        Check(xml.Element("graphicData")!.Element("texPath")!.Value == $"Things/Building/{texture}/{texture}Base"
            && xml.Element("graphicData")!.Element("drawSize")!.Value == (wallMounted ? "(1, 1)" : "(2.4, 1.6)"), "base texture and size contract");
        if (!wallMounted)
        {
        foreach (string rotation in new[] { "North", "South" })
            Check(holoXml.Element("drawOffset" + rotation)!.Value == "(0,0,0.73)", "hologram offset " + rotation);
        foreach (string rotation in new[] { "East", "West" })
            Check(holoXml.Element("drawOffset" + rotation) == null, "hologram lateral offset uses texture alignment " + rotation);
        }
        else
        {
            Check(xml.Element("building")!.Element("isAttachment")!.Value == "true"
                && xml.Element("building")!.Element("isEdifice")!.Value == "false", "wall sign is non-edifice attachment");
            Check(xml.Element("placeWorkers")!.Element("li")!.Value == "Placeworker_AttachedToWall"
                && xml.Element("terrainAffordanceNeeded")!.Attribute("IsNull")!.Value == "True", "wall placement contract");
            foreach (var pair in new Dictionary<string, string> { ["North"] = "(0,0,1.25)", ["South"] = "(0,0,-0.35)", ["West"] = "(-0.55,0,0.45)", ["East"] = "(0.55,0,0.45)" })
                Check(holoXml.Element("drawOffset" + pair.Key)!.Value == pair.Value, "wall projection offset " + pair.Key);
            foreach (var pair in new Dictionary<string, string> { ["North"] = "(0,0,0.9)", ["South"] = "(0,0,-0.9)", ["West"] = "(-0.9,0,0)", ["East"] = "(0.9,0,0)" })
                Check(xml.Element("graphicData")!.Element("drawOffset" + pair.Key)!.Value == pair.Value, "wall base offset " + pair.Key);
        }
        using (var assembly = Mono.Cecil.AssemblyDefinition.ReadAssembly(typeof(CompHoloSignboard).Assembly.Location))
        {
            var draw = assembly.MainModule.Types.Single(t => t.FullName == typeof(CompHoloSignboard).FullName)
                .Methods.Single(m => m.Name == "PostDraw");
            var calls = draw.Body.Instructions.Select(i => i.Operand).OfType<Mono.Cecil.MethodReference>().Select(m => m.Name).ToList();
            foreach (string call in new[] { "IsIlluminated", "MeshAt", "MatAt", "HologramDrawPos", "DrawMesh" })
                Check(calls.Contains(call), "production hologram IL calls " + call);
            var buy = assembly.MainModule.Types.Single(t => t.FullName == "AyameICCT.CommsConsoleShop")
                .NestedTypes.Single(t => t.Name == "Dialog_ShopMerchant").Methods.Single(m => m.Name == "TryBuy");
            Check(buy.Body.Instructions.Count(i => i.Operand is Mono.Cecil.MethodReference m
                && m.DeclaringType.FullName == typeof(LookTargets).FullName && m.Name == ".ctor") == 2,
                "both success and failure messages construct explicit LookTargets for actor-or-building");
        }
        foreach (string language in new[] { "ChineseSimplified", "English" })
        {
            var injected = XDocument.Load(root + $@"Languages\{language}\DefInjected\ThingDef\AyameICCT_Buildings_HoloSignboard.xml").Root!;
            Check(!string.IsNullOrWhiteSpace(injected.Element(defName + ".label")!.Value), language + " sign label");
            Check(injected.Element(defName + ".description")!.Value.Contains(@"\n"), language + " two-paragraph sign description");
            var thoughtLanguage = XDocument.Load(root + $@"Languages\{language}\DefInjected\ThoughtDef\AyameICCT_HoloSignboard.xml").Root!;
            Check(thoughtLanguage.Elements().Count() == 2, language + " thought translations");
            Check(XDocument.Load(root + $@"Languages\{language}\Keyed\AyameICCT_HoloSignboard.xml").Root!.Element("AyameICCT_HoloSignboardContactDesc") != null, language + " direct contact tooltip");
        }
        var chinese = XDocument.Load(root + @"Languages\ChineseSimplified\DefInjected\ThingDef\AyameICCT_Buildings_HoloSignboard.xml").Root!;
        Check(chinese.Element("AyameICCT_WallHoloSignboard.label")!.Value == "壁挂全息茶餐厅加盟招牌"
            && chinese.Element("AyameICCT_WallHoloSignboard.description")!.Value == @"星际茶餐厅加盟店的壁挂式电子招牌，在这里可以线上点单并与茶餐厅联系。\n招牌上循环展示着主厨首推的「黯然销魂饭」，虽然依然是边缘世界流浪艺术家深恶痛绝的红绿配色，但浓郁的叉烧香气仿佛能穿透全息光幕。", "exact wall sign Chinese localization");
        Check(chinese.Element("AyameICCT_HoloSignboard.description")!.Value == @"星际茶餐厅加盟店的电子招牌，在这里可以线上点单并与茶餐厅联系。\n这个招牌的烟火气让人放心，但也偶尔会有行走于边缘世界的流浪艺术家吐槽它的审美。", "exact requested Chinese sign description");

        // Use an isolated actual map and actual production building/comp/job classes.
        var map = NewBlankMap(64);
        map.generatorDef = new MapGeneratorDef();
        var def = new ThingDef
        {
            defName = defName, label = xml.Element("label")!.Value, uiIconPath = xml.Element("uiIconPath")!.Value,
            thingClass = typeof(Building_HoloSignboard), category = ThingCategory.Building,
            useHitPoints = false, passability = wallMounted ? Traversability.Standable : Traversability.PassThroughOnly, pathCost = wallMounted ? 0 : 50,
            size = wallMounted ? new IntVec2(1, 1) : new IntVec2(2, 1), hasInteractionCell = false,
            altitudeLayer = wallMounted ? AltitudeLayer.BuildingOnTop : AltitudeLayer.Building,
            minifiedDef = ThingDefOf.MinifiedThing ??= new ThingDef { defName = "MinifiedThing", thingClass = typeof(MinifiedThing) },
            thingCategories = new List<ThingCategoryDef> { new ThingCategoryDef { defName = "BuildingsMisc" } },
            building = new BuildingProperties { isAttachment = wallMounted, isEdifice = false },
            comps = new List<CompProperties>
            {
                new CompProperties_Power { compClass = typeof(CompPowerTrader) },
                new CompProperties_Flickable(), new CompProperties_Forbiddable(),
                new CompProperties_HoloSignboard { graphicDataExtra = new GraphicData
                {
                    graphicClass = typeof(Graphic_Multi), drawSize = new UnityEngine.Vector2(3.8f, 3.8f),
                    drawOffsetSouth = new UnityEngine.Vector3(0, 0, 0.73f),
                    drawOffsetNorth = new UnityEngine.Vector3(0, 0, 0.73f)
                } }
            }
        };
        MarkSynthetic(def);
        Check(def.Minifiable && def.minifiedDef == ThingDefOf.MinifiedThing && def.thingCategories.Count > 0, defName + " actual ThingDef is minifiable");
        DefDatabase<ThingDef>.Add(def);
        Building? supportWall = null;
        if (wallMounted)
        {
            DesignationDefOf.SmoothFloor ??= new DesignationDef { defName = "SmoothFloor" };
            DesignationDefOf.SmoothWall ??= new DesignationDef { defName = "SmoothWall" };
            var supportDef = new ThingDef { defName = "QA_WallSignSupport", thingClass = typeof(Building), category = ThingCategory.Building,
                useHitPoints = false, fillPercent = 1, blockLight = true, passability = Traversability.Impassable,
                building = new BuildingProperties { isEdifice = true } };
            MarkSynthetic(supportDef); DefDatabase<ThingDef>.Add(supportDef);
            supportWall = (Building)GenSpawn.Spawn(ThingMaker.MakeThing(supportDef), new IntVec3(25, 0, 25), map);
        }
        var sign = (Building_HoloSignboard)ThingMaker.MakeThing(def);
        sign.SetFactionDirect(Faction.OfPlayer);
        GenSpawn.Spawn(sign, new IntVec3(25, 0, 25), map, Rot4.South);
        if (wallMounted) Check(supportWall!.Spawned && sign.Spawned && supportWall.Position == sign.Position, "wall sign shares its occupied cell with an impassable supporting wall");
        void Power(bool on) => Field(typeof(CompPowerTrader), "powerOnInt").SetValue(sign.GetComp<CompPowerTrader>(), on);
        void Flick(bool on) => Field(typeof(CompFlickable), "switchOnInt").SetValue(sign.GetComp<CompFlickable>(), on);
        bool Context(Pawn? actor = null) => (bool)ShopPurchaseType.GetMethod("IsContextValid", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, new object?[] { sign, actor })!;
        Command_Action Command() => sign.GetGizmos().OfType<Command_Action>().Single(c => c.defaultLabel == "AyameICCT_ContactRestaurant".Translate());
        var terminalType = typeof(Building_HoloSignboard).Assembly.GetType("AyameICCT.RestaurantTerminal")!;
        bool Lit() => (bool)terminalType.GetMethod("IsIlluminated", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, new object[] { sign })!;
        Power(true); Flick(true);
        var graphics = ((CompProperties_HoloSignboard)sign.GetComp<CompHoloSignboard>().props).graphicDataExtra;
        if (wallMounted)
        {
            graphics.drawOffsetNorth = new UnityEngine.Vector3(0, 0, 1.25f);
            graphics.drawOffsetSouth = new UnityEngine.Vector3(0, 0, -0.35f);
            graphics.drawOffsetWest = new UnityEngine.Vector3(-0.55f, 0, 0.45f);
            graphics.drawOffsetEast = new UnityEngine.Vector3(0.55f, 0, 0.45f);
        }
        if (!wallMounted)
        {
        foreach (var rotation in new[] { Rot4.North, Rot4.South })
            Check(graphics.DrawOffsetForRot(rotation) == new UnityEngine.Vector3(0, 0, 0.73f), "actual GraphicData resolves offset " + rotation);
        foreach (var rotation in new[] { Rot4.East, Rot4.West })
            Check(graphics.DrawOffsetForRot(rotation) == UnityEngine.Vector3.zero, "actual GraphicData resolves zero offset " + rotation);
        }
        Check(Context() && Lit(), "powered sign is lit and supports pawn-less purchases");
        Check(!(bool)Field(typeof(Gizmo), "disabled").GetValue(Command())!, "player-owned powered sign provides enabled contact Gizmo");
        foreach (var rotation in new[] { Rot4.North, Rot4.East, Rot4.South, Rot4.West })
        {
            sign.Rotation = rotation;
            var drawPos = (UnityEngine.Vector3)typeof(CompHoloSignboard).GetMethod("HologramDrawPos", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, new object[] { sign, graphics })!;
            Check(drawPos.y >= Altitudes.AltitudeFor(AltitudeLayer.MoteOverhead)
                && drawPos.y > Altitudes.AltitudeFor(AltitudeLayer.Building)
                && drawPos.y > Altitudes.AltitudeFor(AltitudeLayer.BuildingOnTop), "projection clears north wall and wall top " + rotation);
            var offsetPos = sign.DrawPos + graphics.DrawOffsetForRot(rotation);
            Check(drawPos.x == offsetPos.x && drawPos.z == offsetPos.z && drawPos.y > sign.DrawPos.y, "height fix preserves directional alignment and clears base " + rotation);
            var worker = QaWorkerOn(map, sign.Position + new IntVec3(-1, 0, -1));
            Check(worker.CanReach(sign, PathEndMode.Touch, Danger.Some) && Context(worker), "native Touch pathfinding and adjacent purchase " + rotation);
            Check((PathEndMode)terminalType.GetMethod("ApproachMode", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, new object[] { sign })! == PathEndMode.Touch, "production sign approach uses Touch");
            worker.DeSpawn();
        }
        sign.Rotation = Rot4.South;
        Power(false);
        Check((bool)Field(typeof(Gizmo), "disabled").GetValue(Command())! && !Context() && !Lit(), "power loss disables Gizmo, purchase and projection together");
        int before = ShopWindows().Count;
        Command().action();
        Check(ShopWindows().Count == before, "direct invocation of disabled Gizmo opens nothing");
        sign.GetComp<CompHoloSignboard>().PostDraw();
        Check(true, "unpowered projection does not resolve or draw graphics");
        Power(true); Flick(false);
        Check((bool)Field(typeof(Gizmo), "disabled").GetValue(Command())! && !Context() && !Lit(), "switch-off disables Gizmo, purchase and projection together");
        Flick(true);
        var flareDef = new GameConditionDef { defName = "QA_SignSolarFlare", conditionClass = typeof(QaSignFlare) };
        var flare = GameConditionMaker.MakeCondition(flareDef, 1000);
        map.gameConditionManager.RegisterCondition(flare);
        Check((bool)Field(typeof(Gizmo), "disabled").GetValue(Command())! && Command().disabledReason == "CannotUseSolarFlare".Translate() && !Context() && !Lit(), "solar flare disables Gizmo with reason and hides projection");
        map.gameConditionManager.ActiveConditions.Remove(flare);
        Check(Context() && !(bool)Field(typeof(Gizmo), "disabled").GetValue(Command())!, "sign recovers when solar flare ends");
        sign.SetFactionDirect(new Faction { def = new FactionDef { defName = "QA_SignEnemy" }, loadID = 99117 });
        Check(!sign.GetGizmos().OfType<Command_Action>().Any(c => c.defaultLabel == "AyameICCT_ContactRestaurant".Translate()) && !Context(), "enemy sign has no contact Gizmo and cannot buy");
        sign.SetFactionDirect(Faction.OfPlayer);

        Command().action();
        var window = ShopWindows().Last();
        Check(ShopWindows().Count == before + 1 && Field(ShopWindowType, "actor").GetValue(window) == null, "Gizmo opens real merchant window without actor");
        Check(WindowCanBuy(window, "None", 50) == (CountHomeSilver(map) >= 50), "pawn-less window uses real quote/context/silver gate");
        AddHomeSilver(map, new IntVec3(40, 0, 40), 200);
        int silver = CountHomeSilver(map), pods = ShopPods(map).Count;
        SetSlider(window, "granuleSlider", 500); SetSlider(window, "sheetSlider", 500);
        InvokeWindow(window, "BuyPlastic");
        Check(CountHomeSilver(map) == silver - 130 && ShopPods(map).Count == pods + 1, "Gizmo -> pawn-less merchant -> quote -> Home silver debit -> native pod");
        Check(GoodsTotal(PodContents(ShopPods(map).Last()), shopGranuleDef!) == 500
            && GoodsTotal(PodContents(ShopPods(map).Last()), shopSheetDef!) == 500, "pawn-less delivery has exact whole order");
        Check(!Find.WindowStack.IsOpen(window), "pawn-less success closes shop");
        InvokeWindow(window, "BuyPlastic");
        Check(CountHomeSilver(map) == silver - 130 && ShopPods(map).Count == pods + 1, "pawn-less repeat Buy is idempotent");
        Command().action(); window = ShopWindows().Last();
        SetSlider(window, "granuleSlider", 500);
        Power(false); silver = CountHomeSilver(map); pods = ShopPods(map).Count;
        InvokeWindow(window, "BuyPlastic");
        Check(CountHomeSilver(map) == silver && ShopPods(map).Count == pods, "power loss after opening pawn-less shop mutates nothing");
        Power(true); window.Close();

        var pawn = QaWorkerOn(map, sign.Position + new IntVec3(-1, 0, -1));
        PrepareMenuOrdering(pawn);
        var option = sign.GetFloatMenuOptions(pawn).Single(o => o.Label == "AyameICCT_ContactRestaurant".Translate());
        Check(option.action != null, "sign right-click contact is reachable and enabled");
        before = ShopWindows().Count; option.action!();
        Check(ShopWindows().Count == before, "right-click still orders movement instead of directly opening");
        Job job = pawn.jobs.curJob != null && pawn.jobs.curJob.def == shopJobDef
            ? pawn.jobs.curJob : Enumerable.Range(0, pawn.jobs.jobQueue.Count)
                .Select(i => pawn.jobs.jobQueue[i].job).First(j => j.def == shopJobDef);
        Check(job.def == shopJobDef && job.targetA.Thing == sign, "right-click orders production job targeting sign");
        pawn.jobs.ClearQueuedJobs(canReturnToPool: false); ReleaseAllReservations(pawn);
        var driver = new JobDriver_ContactRestaurant { pawn = pawn, job = JobMaker.MakeJob(shopJobDef!, sign) };
        Check(driver.TryMakePreToilReservations(false), "sign job preflight reserves actual reachable sign");
        var toils = ContactToils(driver); toils.Last().actor = pawn; toils.Last().initAction();
        Check(toils[0].defaultCompleteMode == ToilCompleteMode.PatherArrival, "contact job retains native arrival-controlled movement toil");
        Check(ShopWindows().Count == before + 1 && Field(ShopWindowType, "actor").GetValue(ShopWindows().Last()) == pawn, "sign arrival toil opens real merchant with actor");
        window = ShopWindows().Last(); AddHomeSilver(map, new IntVec3(41, 0, 40), 100);
        silver = CountHomeSilver(map); pods = ShopPods(map).Count;
        SetSlider(window, "granuleSlider", 500); InvokeWindow(window, "BuyPlastic");
        Check(CountHomeSilver(map) == silver - 50 && ShopPods(map).Count == pods + 1, "right-click sign merchant purchase also spends and delivers");
        pawn.Position = sign.Position + new IntVec3(0, 0, 4);
        Check(!Context(pawn), "actor-bound purchase requires immediate Touch rather than distant reachability");
        ReleaseAllReservations(pawn);

        var thoughtXml = XDocument.Load(root + @"Defs\ThoughtDefs\AyameICCT_HoloSignboard.xml").Root!.Element("ThoughtDef")!;
        Check(thoughtXml.Element("workerClass")!.Value == typeof(ThoughtWorker_SawStrangeSignboard).FullName
            && thoughtXml.Element("thoughtClass")!.Value == nameof(Thought_Situational)
            && thoughtXml.Element("validWhileDespawned")!.Value == "false", "sign thought is situational, not a memory");
        Check(thoughtXml.Element("requiredTraits")!.Element("li")!.Value == "TorturedArtist"
            && thoughtXml.Element("stages")!.Element("li")!.Element("baseMoodEffect")!.Value == "-6", "thought XML requires TorturedArtist and gives -6");
        var artist = DefDatabase<TraitDef>.GetNamed("TorturedArtist", false);
        if (artist == null)
        {
            artist = new TraitDef { defName = "TorturedArtist", degreeDatas = new List<TraitDegreeData> { new TraitDegreeData() } };
            DefDatabase<TraitDef>.Add(artist);
        }
        PawnCapacityDefOf.Sight ??= new PawnCapacityDef { defName = "Sight", workerClass = typeof(PawnCapacityWorker), minForCapable = 0 };
        PawnCapacityDefOf.Consciousness ??= new PawnCapacityDef { defName = "Consciousness", workerClass = typeof(PawnCapacityWorker), minForCapable = 0 };
        foreach (var capacity in new[] { PawnCapacityDefOf.Sight, PawnCapacityDefOf.Consciousness })
            if (!DefDatabase<PawnCapacityDef>.AllDefsListForReading.Contains(capacity)) DefDatabase<PawnCapacityDef>.Add(capacity);
        pawn.health.capacities.Clear();
        pawn.story = new Pawn_StoryTracker(pawn);
        pawn.story.traits.allTraits.Add(new Trait(artist));
        var thought = new ThoughtWorker_SawStrangeSignboard();
        bool Active() => ((ThoughtState)typeof(ThoughtWorker_SawStrangeSignboard).GetMethod("CurrentStateInternal", BindingFlags.NonPublic | BindingFlags.Instance)!.Invoke(thought, new object[] { pawn })!).Active;
        Check(Active(), "awake sighted TorturedArtist sees powered sign within 10 tiles");
        pawn.Position = sign.Position + new IntVec3(0, 0, 11);
        Check(!Active(), "leaving observation radius deactivates thought on next evaluation");
        pawn.Position = sign.Position + new IntVec3(0, 0, 4);
        DesignationDefOf.SmoothFloor ??= new DesignationDef { defName = "SmoothFloor" };
        DesignationDefOf.SmoothWall ??= new DesignationDef { defName = "SmoothWall" };
        var wallDef = new ThingDef { defName = "QA_SignWall", thingClass = typeof(Building), category = ThingCategory.Building,
            useHitPoints = false, fillPercent = 1, blockLight = true, passability = Traversability.Impassable, building = new BuildingProperties() };
        MarkSynthetic(wallDef); DefDatabase<ThingDef>.Add(wallDef);
        var wall = GenSpawn.Spawn(ThingMaker.MakeThing(wallDef), sign.Position + new IntVec3(0, 0, 2), map);
        Check(!Active(), "wall blocks native GenSight and deactivates thought");
        wall.DeSpawn(); Check(Active(), "regaining sight immediately restores thought");
        Power(false); Check(!Active(), "unpowered hologram produces no artist debuff");
        Power(true); Flick(false); Check(!Active(), "switched-off hologram produces no artist debuff");
        Flick(true); pawn.story.traits.allTraits.Clear(); Check(!Active(), "non-TorturedArtist sees no debuff");
        pawn.story.traits.allTraits.Add(new Trait(artist));
        float sightMin = PawnCapacityDefOf.Sight.minForCapable;
        PawnCapacityDefOf.Sight.minForCapable = 2;
        try { Check(!Active(), "blind artist sees no debuff"); }
        finally { PawnCapacityDefOf.Sight.minForCapable = sightMin; }
        var sleepJob = new JobDef { defName = "QA_SignSleeping", driverClass = typeof(JobDriver_Wait) };
        pawn.jobs.curJob = JobMaker.MakeJob(sleepJob);
        pawn.jobs.curDriver = new JobDriver_Wait { pawn = pawn, job = pawn.jobs.curJob, asleep = true };
        Check(!Active(), "sleeping artist sees no debuff");
        pawn.jobs.curDriver.asleep = false; Check(Active(), "waking restores current sight thought");
        pawn.DeSpawn(); Check(!Active(), "despawned artist sees no debuff");
        sign.DeSpawn();
        supportWall?.DeSpawn();
        Check(!Context() && (bool)Field(typeof(Gizmo), "disabled").GetValue(Command())! && !Lit(), "despawned sign disables all use and projection");
    }
}

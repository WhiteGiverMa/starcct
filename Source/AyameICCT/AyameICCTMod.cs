using UnityEngine;
using Verse;

namespace AyameICCT
{
    public class PackagingSettings : ModSettings
    {
        public bool IncludeNutrientPaste = true;
        public bool IncludeKibble;
        public bool AllowRepackaging;

        public override void ExposeData()
        {
            Scribe_Values.Look(ref IncludeNutrientPaste, "includeNutrientPaste", true);
            Scribe_Values.Look(ref IncludeKibble, "includeKibble", false);
            Scribe_Values.Look(ref AllowRepackaging, "allowRepackaging", false);
        }
    }

    public class AyameICCTMod : Mod
    {
        public const string PackageId = "ayame.interstellarchachaanteng";
        public static PackagingSettings Settings { get; private set; }

        public AyameICCTMod(ModContentPack content) : base(content)
        {
            Settings = GetSettings<PackagingSettings>();
            ModPatches.Install();
        }

        public override string SettingsCategory()
        {
            return "AyameICCT_ModName".Translate();
        }

        public override void DoSettingsWindowContents(Rect inRect)
        {
            bool paste = Settings.IncludeNutrientPaste;
            bool kibble = Settings.IncludeKibble;
            bool repackaging = Settings.AllowRepackaging;
            Listing_Standard listing = new Listing_Standard();
            listing.Begin(inRect);
            listing.CheckboxLabeled("AyameICCT_IncludeNutrientPaste".Translate(), ref Settings.IncludeNutrientPaste,
                "AyameICCT_IncludeNutrientPasteTip".Translate());
            listing.CheckboxLabeled("AyameICCT_IncludeKibble".Translate(), ref Settings.IncludeKibble,
                "AyameICCT_IncludeKibbleTip".Translate());
            listing.CheckboxLabeled("AyameICCT_AllowRepackaging".Translate(), ref Settings.AllowRepackaging,
                "AyameICCT_AllowRepackagingTip".Translate());
            listing.Gap();
            listing.Label("AyameICCT_FoodRules".Translate());
            listing.Gap();
            listing.Label("AyameICCT_FilterChanges".Translate());
            listing.End();

            if (paste != Settings.IncludeNutrientPaste || kibble != Settings.IncludeKibble
                || repackaging != Settings.AllowRepackaging)
            {
                PackagingFoodFilter.Apply(Settings);
            }
        }
    }
}

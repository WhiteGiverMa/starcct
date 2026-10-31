using HarmonyLib;
using Verse;

namespace AyameICCT
{
    internal static class ModPatches
    {
        private static bool installed;

        internal static void Install()
        {
            if (installed)
            {
                return;
            }
            Harmony harmony = new Harmony(AyameICCTMod.PackageId);
            harmony.Patch(AccessTools.PropertyGetter(typeof(ModMetaData), nameof(ModMetaData.Name)),
                postfix: new HarmonyMethod(typeof(ModPatches), nameof(MetadataName)));
            harmony.Patch(AccessTools.PropertyGetter(typeof(ModMetaData), nameof(ModMetaData.Description)),
                postfix: new HarmonyMethod(typeof(ModPatches), nameof(MetadataDescription)));
            harmony.Patch(AccessTools.PropertyGetter(typeof(ModContentPack), nameof(ModContentPack.Name)),
                postfix: new HarmonyMethod(typeof(ModPatches), nameof(ContentName)));
            harmony.Patch(AccessTools.Method(typeof(PlayDataLoader), "ResetStaticDataPost"),
                postfix: new HarmonyMethod(typeof(ModPatches), nameof(AfterDefsResolved)));
            installed = true;
        }

        private static void AfterDefsResolved()
        {
            PackagingFoodFilter.Apply(AyameICCTMod.Settings);
        }

        private static void MetadataName(ModMetaData __instance, ref string __result)
        {
            if (__instance.packageIdLowerCase == AyameICCTMod.PackageId)
            {
                Localize("AyameICCT_ModName", ref __result);
            }
        }

        private static void MetadataDescription(ModMetaData __instance, ref string __result)
        {
            if (__instance.packageIdLowerCase == AyameICCTMod.PackageId)
            {
                Localize("AyameICCT_ModDescription", ref __result);
            }
        }

        private static void ContentName(ModContentPack __instance, ref string __result)
        {
            if (__instance.PackageId == AyameICCTMod.PackageId)
            {
                Localize("AyameICCT_ModName", ref __result);
            }
        }

        private static void Localize(string key, ref string result)
        {
            // Never load or translate language data from metadata getters during startup.
            LoadedLanguage language = LanguageDatabase.activeLanguage;
            if (language != null && language.keyedReplacements.TryGetValue(key, out LoadedLanguage.KeyedReplacement text)
                && !text.isPlaceholder && !string.IsNullOrEmpty(text.value))
            {
                result = text.value;
            }
        }
    }
}

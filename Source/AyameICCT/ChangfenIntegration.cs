using System.Linq;
using RimWorld;
using Verse;

namespace AyameICCT
{
    public static class ChangfenIntegration
    {
        private static readonly string[] RecipeNames =
        {
            "AyameICCT_Make_Changfen",
            "AyameICCT_Make_Changfen_Bulk",
            "AyameICCT_Make_ZhuChangfen",
            "AyameICCT_Make_ZhuChangfen_Bulk"
        };

        private static readonly string[] OptionalIngredientNames = { "RawToxipotato", "DMSE_Carbohydrate" };

        public static bool IsChangfen(ThingDef def)
        {
            return def != null && (def.defName == "AyameICCT_Changfen" || def.defName == "AyameICCT_ZhuChangfen");
        }

        public static void Apply()
        {
            ThingDef[] optionalIngredients = OptionalIngredientNames
                .Select(name => DefDatabase<ThingDef>.GetNamedSilentFail(name))
                .Where(def => def != null)
                .ToArray();
            if (optionalIngredients.Length == 0)
            {
                return;
            }

            foreach (RecipeDef recipe in DefDatabase<RecipeDef>.AllDefs.Where(def => RecipeNames.Contains(def.defName)))
            {
                if (recipe.ingredients == null || recipe.ingredients.Count == 0)
                {
                    continue;
                }

                foreach (ThingDef ingredient in optionalIngredients)
                {
                    recipe.ingredients[0].filter.SetAllow(ingredient, true);
                    recipe.fixedIngredientFilter?.SetAllow(ingredient, true);
                    recipe.defaultIngredientFilter?.SetAllow(ingredient, true);
                }
            }
        }
    }
}

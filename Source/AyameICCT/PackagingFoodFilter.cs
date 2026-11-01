using System.Linq;
using RimWorld;
using Verse;

namespace AyameICCT
{
    public static class PackagingFoodFilter
    {
        public static bool IsCombatRation(ThingDef def)
        {
            return def.defName == "DMS_CombatRation";
        }

        internal static bool IsPreparedIngredient(ThingDef def)
        {
            return def.category == ThingCategory.Item && def.ingestible != null && !def.IsCorpse
                && (IsCombatRation(def) || (!def.IsDrug
                    && !def.IsWithinCategory(ThingCategoryDefOf.Drugs)
                    && !def.IsWithinCategory(DefDatabase<ThingCategoryDef>.GetNamed("FoodRaw"))
                    && ((def.ingestible.foodType & (FoodTypeFlags.Meal | FoodTypeFlags.Processed | FoodTypeFlags.Kibble)) != 0
                        || def.IsWithinCategory(DefDatabase<ThingCategoryDef>.GetNamed("FoodMeals")))));
        }

        public static bool CanPack(ThingDef def, PackagingSettings settings)
        {
            if (def.category != ThingCategory.Item || def.ingestible == null
                || def.IsCorpse || (def == ThingDefOf.MealSurvivalPack && !settings.AllowRepackaging))
            {
                return false;
            }

            if (IsCombatRation(def))
            {
                return true;
            }

            if (!def.ingestible.HumanEdible || def.IsDrug
                || def.IsWithinCategory(ThingCategoryDefOf.Drugs)
                || def.IsWithinCategory(DefDatabase<ThingCategoryDef>.GetNamed("FoodRaw"))
                || !def.IsNutritionGivingIngestible)
            {
                return false;
            }

            float nutrition = def.GetStatValueAbstract(StatDefOf.Nutrition);
            if (!(nutrition > 0f) || float.IsInfinity(nutrition))
            {
                return false;
            }

            if (def == ThingDefOf.MealNutrientPaste && !settings.IncludeNutrientPaste)
            {
                return false;
            }

            if ((def.ingestible.foodType & FoodTypeFlags.Kibble) != 0)
            {
                return settings.IncludeKibble;
            }

            // ponytail: trust resolved food semantics, not recipes (which also manufacture raw meat).
            return (def.ingestible.foodType & (FoodTypeFlags.Meal | FoodTypeFlags.Processed)) != 0
                || def.IsWithinCategory(DefDatabase<ThingCategoryDef>.GetNamed("FoodMeals"));
        }

        public static void Apply(PackagingSettings settings)
        {
            if (!ThingDefOf.MealSurvivalPack.comps.Any(comp => comp.compClass == typeof(CompPackagingIngredients)))
            {
                ThingDefOf.MealSurvivalPack.comps.Insert(0, new CompProperties(typeof(CompPackagingIngredients)));
            }
            ThingDef[] foods = DefDatabase<ThingDef>.AllDefs.Where(def => CanPack(def, settings)).ToArray();
            foreach (RecipeDef recipe in DefDatabase<RecipeDef>.AllDefs.Where(def =>
                def.defName == "AyameICCT_Pack_Meal_5"
                || def.defName == "AyameICCT_Pack_Meal_9"
                || def.defName == "AyameICCT_Pack_Meal_13"))
            {
                ThingFilter foodFilter = recipe.ingredients[1].filter;
                foreach (ThingDef def in foodFilter.AllowedThingDefs.ToArray())
                {
                    foodFilter.SetAllow(def, false);
                    recipe.fixedIngredientFilter.SetAllow(def, false);
                    recipe.defaultIngredientFilter.SetAllow(def, false);
                }

                foreach (ThingDef def in foods)
                {
                    if (recipe.products.Any(product => product.thingDef == def)
                        && !(def == ThingDefOf.MealSurvivalPack && settings.AllowRepackaging))
                    {
                        continue;
                    }
                    foodFilter.SetAllow(def, true);
                    recipe.fixedIngredientFilter.SetAllow(def, true);
                    recipe.defaultIngredientFilter.SetAllow(def, true);
                }
            }
        }
    }
}

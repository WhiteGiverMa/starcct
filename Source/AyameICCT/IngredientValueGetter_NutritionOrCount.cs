using System.Linq;
using RimWorld;
using Verse;

namespace AyameICCT
{
    // All foods use nutrition equally; only the DMS ration has a packaging-specific value.
    public class IngredientValueGetter_NutritionOrCount : IngredientValueGetter
    {
        private readonly IngredientValueGetter_Nutrition nutrition = new IngredientValueGetter_Nutrition();
        private readonly IngredientValueGetter_Volume volume = new IngredientValueGetter_Volume();

        public override float ValuePerUnitOf(ThingDef t)
        {
            if (PackagingFoodFilter.IsCombatRation(t))
            {
                return 2f;
            }
            return t.IsNutritionGivingIngestible
                ? nutrition.ValuePerUnitOf(t)
                : volume.ValuePerUnitOf(t);
        }

        public override string BillRequirementsDescription(RecipeDef r, IngredientCount ing)
        {
            return ing.filter.AllowedThingDefs.All(t => t.IsNutritionGivingIngestible || PackagingFoodFilter.IsCombatRation(t))
                ? nutrition.BillRequirementsDescription(r, ing)
                : volume.BillRequirementsDescription(r, ing);
        }

        public override string ExtraDescriptionLine(RecipeDef r)
        {
            return volume.ExtraDescriptionLine(r);
        }
    }
}

using System.Linq;
using RimWorld;
using Verse;

namespace AyameICCT
{
    // Food uses nutrition; everything else follows vanilla volume accounting.
    public class IngredientValueGetter_NutritionOrCount : IngredientValueGetter
    {
        private readonly IngredientValueGetter_Nutrition nutrition = new IngredientValueGetter_Nutrition();
        private readonly IngredientValueGetter_Volume volume = new IngredientValueGetter_Volume();

        public override float ValuePerUnitOf(ThingDef t)
        {
            return t.IsNutritionGivingIngestible
                ? nutrition.ValuePerUnitOf(t)
                : volume.ValuePerUnitOf(t);
        }

        public override string BillRequirementsDescription(RecipeDef r, IngredientCount ing)
        {
            return ing.filter.AllowedThingDefs.All(t => t.IsNutritionGivingIngestible)
                ? nutrition.BillRequirementsDescription(r, ing)
                : volume.BillRequirementsDescription(r, ing);
        }

        public override string ExtraDescriptionLine(RecipeDef r)
        {
            return volume.ExtraDescriptionLine(r);
        }
    }
}

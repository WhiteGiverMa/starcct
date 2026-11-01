using RimWorld;
using Verse;

namespace AyameICCT
{
    public sealed class CompPackagingIngredients : ThingComp
    {
        public override void Notify_RecipeProduced(Pawn pawn)
        {
            RemovePackaging(parent);
        }

        public override void PreAbsorbStack(Thing otherStack, int count)
        {
            // ponytail: vanilla merges records even at count zero; clean before its three-ingredient cap.
            RemovePackaging(parent);
            RemovePackaging(otherStack);
        }

        private static void RemovePackaging(Thing thing)
        {
            thing.TryGetComp<CompIngredients>()?.ingredients.RemoveAll(def => def.defName == "AyameICCT_PlasticSheet");
        }
    }
}

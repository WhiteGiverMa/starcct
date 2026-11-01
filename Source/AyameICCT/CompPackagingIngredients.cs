using System.Collections.Generic;
using System.Linq;
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

        public override void PostIngested(Pawn ingester)
        {
            if (AyameICCTMod.Settings?.InheritIngredientMood != true
                || parent.def != ThingDefOf.MealSurvivalPack
                || ingester.needs?.mood == null || ingester.story?.traits == null)
            {
                return;
            }
            CompIngredients ingredients = parent.TryGetComp<CompIngredients>();
            if (ingredients == null)
            {
                return;
            }
            HashSet<ThoughtDef> seen = new HashSet<ThoughtDef>(
                FoodUtility.ThoughtsFromIngesting(ingester, parent, parent.def).Select(thought => thought.thought));
            foreach (ThingDef def in ingredients.ingredients.Where(PackagingFoodFilter.IsPreparedIngredient).Distinct())
            {
                // ponytail: a def-only probe reuses native mood rules, never ingestion effects or nested ingredients.
                Thing probe = new Thing { def = def };
                foreach (FoodUtility.ThoughtFromIngesting thought in FoodUtility.ThoughtsFromIngesting(ingester, probe, def).ToArray())
                {
                    if (!seen.Add(thought.thought))
                    {
                        continue;
                    }
                    Thought_Memory memory = ThoughtMaker.MakeThought(thought.thought, thought.fromPrecept);
                    if (memory is Thought_FoodEaten eaten)
                    {
                        eaten.SetFood(probe);
                    }
                    ingester.needs.mood.thoughts.memories.TryGainMemory(memory);
                }
            }
        }

        private static void RemovePackaging(Thing thing)
        {
            thing.TryGetComp<CompIngredients>()?.ingredients.RemoveAll(def => def.defName == "AyameICCT_PlasticSheet");
        }
    }
}

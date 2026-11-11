using System.Collections.Generic;
using RimWorld;
using Verse;
using Verse.AI;

namespace AyameICCT
{
    public sealed class JobDriver_ContactRestaurant : JobDriver
    {
        private Building Console => job.targetA.Thing as Building;

        public override bool TryMakePreToilReservations(bool errorOnFailed)
        {
            Building console = Console;
            if (console == null || !console.Spawned || console.Map != pawn.Map
                || console.Faction != Faction.OfPlayer || console.IsForbidden(pawn)
                || !RestaurantTerminal.CanUseNow(console)
                || !pawn.CanReach(console, RestaurantTerminal.ApproachMode(console), Danger.Some))
            {
                JobFailReason.Is("AyameICCT_ShopUnavailable".Translate());
                return false;
            }
            return pawn.Reserve(job.targetA, job, 1, -1, null, errorOnFailed);
        }

        protected override IEnumerable<Toil> MakeNewToils()
        {
            this.FailOnDespawnedOrNull(TargetIndex.A);
            yield return Toils_Goto.GotoThing(TargetIndex.A, RestaurantTerminal.ApproachMode(Console))
                .FailOn(to => !(to.actor.jobs.curJob.GetTarget(TargetIndex.A).Thing is Building console)
                    || !RestaurantTerminal.CanUseNow(console));
            Toil openShop = ToilMaker.MakeToil("ContactRestaurantOpenShop");
            openShop.initAction = () => OpenShop(openShop.actor);
            yield return openShop;
        }

        private void OpenShop(Pawn actor)
        {
            Building console = Console;
            if (console == null || actor == null || !actor.Spawned || !console.Spawned
                || console.Map == null || console.Map != actor.Map
                || console.Faction != Faction.OfPlayer || console.IsForbidden(actor)
                || !RestaurantTerminal.CanUseNow(console)
                || !actor.health.capacities.CapableOf(PawnCapacityDefOf.Talking)
                || !RestaurantTerminal.IsAtTerminal(console, actor))
            {
                Messages.Message("AyameICCT_ShopUnavailable".Translate(), actor,
                    MessageTypeDefOf.RejectInput, historical: false);
                EndJobWith(JobCondition.Incompletable);
                return;
            }
            Find.WindowStack.Add(new CommsConsoleShop.Dialog_ShopMerchant(console, actor));
        }
    }
}

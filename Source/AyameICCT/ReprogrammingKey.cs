using System;
using RimWorld;
using Verse;
using Verse.AI;

namespace AyameICCT
{
    internal static class ReprogrammingKeyUtility
    {
        internal static AcceptanceReport GetCost(Corpse corpse, out int cost)
        {
            cost = 0;
            Pawn mech = corpse?.InnerPawn;
            if (corpse == null || corpse.Destroyed || mech == null || !mech.Dead
                || !mech.RaceProps.IsMechanoid || mech.Faction == Faction.OfPlayer)
            {
                return "AyameICCT_KeyInvalidTarget".Translate();
            }
            float bandwidth = mech.GetStatValue(StatDefOf.BandwidthCost);
            double rounded = Math.Ceiling((double)bandwidth);
            if (!float.IsFinite(bandwidth) || bandwidth < 0f || rounded > int.MaxValue)
            {
                return "AyameICCT_KeyInvalidBandwidth".Translate(bandwidth.ToString());
            }
            cost = (int)rounded;
            return true;
        }

        internal static int CountInventory(Pawn pawn, ThingDef keyDef, int limit)
        {
            int count = 0;
            foreach (Thing thing in pawn.inventory.innerContainer)
            {
                if (thing.def == keyDef)
                {
                    count += Math.Min(thing.stackCount, limit - count);
                    if (count == limit)
                    {
                        break;
                    }
                }
            }
            return count;
        }
    }

    public sealed class CompUsable_ReprogrammingKey : CompUsable
    {
        protected override string FloatMenuOptionLabel(Pawn pawn)
        {
            return "AyameICCT_KeyUse".Translate(parent.Label);
        }

        public override void TryStartUseJob(Pawn pawn, LocalTargetInfo extraTarget, bool forced = false)
        {
            AcceptanceReport report = CanBeUsedBy(pawn, forced);
            if (!report)
            {
                SendCannotUseMessage(pawn, report.Reason);
                return;
            }
            report = ReprogrammingKeyUtility.GetCost(extraTarget.Thing as Corpse, out int cost);
            if (!report)
            {
                SendCannotUseMessage(pawn, report.Reason);
                return;
            }
            Job job = JobMaker.MakeJob(Props.useJob, extraTarget, parent);
            job.count = cost;
            job.checkEncumbrance = true;
            if (!pawn.jobs.TryTakeOrderedJob(job, JobTag.Misc))
            {
                SendCannotUseMessage(pawn, JobFailReason.Reason.NullOrEmpty()
                    ? "AyameICCT_KeyStartFailed".Translate().Resolve() : JobFailReason.Reason);
            }
        }
    }

    public sealed class CompTargetable_ReprogrammingKey : CompTargetable_SingleCorpse
    {
        public override bool ValidateTarget(LocalTargetInfo target, bool showMessages = true)
        {
            AcceptanceReport report = ReprogrammingKeyUtility.GetCost(target.Thing as Corpse, out _);
            if (!report && showMessages)
            {
                Messages.Message(report.Reason, MessageTypeDefOf.RejectInput, historical: false);
            }
            return report && base.ValidateTarget(target, showMessages);
        }
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;

namespace AyameICCT
{
    public sealed class JobDriver_ReprogramMech : JobDriver
    {
        // ponytail: vanilla multi-stack ThingOwner has 999999 slots; keep source stacks separate, never overstack.
        private const int InventoryStackLimit = 999999;
        private const float StagingRadius = 12.9f;
        private int requiredCost = -1;
        private ThingDef keyDef;
        // Preflight chooses this once when the full payment cannot fit the inventory.
        // Once a later capacity change forces batching it stays on for this job.
        private bool batchMode;

        private Corpse Corpse => job.targetA.Thing as Corpse;

        public override void ExposeData()
        {
            base.ExposeData();
            Scribe_Values.Look(ref requiredCost, "requiredCost", -1);
            Scribe_Defs.Look(ref keyDef, "keyDef");
            Scribe_Values.Look(ref batchMode, "batchMode", false);
        }

        public override bool TryMakePreToilReservations(bool errorOnFailed)
        {
            AcceptanceReport report = ReprogrammingKeyUtility.GetCost(Corpse, out requiredCost);
            if (!report)
            {
                JobFailReason.Is(report.Reason);
                return false;
            }
            keyDef = DefDatabase<ThingDef>.GetNamed("AyameICCT_ReprogrammingKey");
            if (!TargetAvailable() || !pawn.CanReserve(Corpse)
                || !pawn.CanReach(Corpse, PathEndMode.Touch, Danger.Deadly))
            {
                JobFailReason.Is("AyameICCT_KeyTargetUnavailable".Translate());
                return false;
            }

            int remaining = requiredCost - ReprogrammingKeyUtility.CountInventory(pawn, keyDef, requiredCost);
            var sources = new List<LocalTargetInfo>();
            var counts = new List<int>();
            double addedMass = 0;
            bool canUseInventory = true;
            if (remaining > 0)
            {
                foreach (Thing source in pawn.Map.listerThings.GetAllThings(t => t.def == keyDef, lookInHaulSources: true)
                    .Distinct().OrderBy(t => t == job.targetB.Thing ? 0 : 1)
                    .ThenBy(t => (t.PositionHeld - pawn.Position).LengthHorizontalSquared))
                {
                    if (!SourceAvailable(source) || !pawn.CanReserve(source)
                        || !pawn.CanReach(source.SpawnedParentOrMe, PathEndMode.ClosestTouch, Danger.Deadly))
                    {
                        continue;
                    }
                    int take = Math.Min(remaining, source.stackCount);
                    float mass = source.GetStatValue(StatDefOf.Mass);
                    if (!float.IsFinite(mass) || mass < 0f)
                    {
                        // Unknown mass cannot be proven to fit the inventory; hand carry is still safe.
                        canUseInventory = false;
                    }
                    else
                    {
                        addedMass += (double)take * mass;
                    }
                    sources.Add(source);
                    counts.Add(take);
                    remaining -= take;
                    if (remaining == 0)
                    {
                        break;
                    }
                }
            }
            if (remaining > 0)
            {
                JobFailReason.Is("AyameICCT_KeyMissing".Translate(requiredCost));
                return false;
            }
            if (!canUseInventory || !HasCapacity(addedMass, sources.Count))
            {
                batchMode = true;
                if (sources.Count > 0 && pawn.carryTracker.MaxStackSpaceEver(keyDef) < 1)
                {
                    JobFailReason.Is("AyameICCT_KeyCapacity".Translate());
                    return false;
                }
            }
            else
            {
                batchMode = false;
            }
            if (!pawn.Reserve(Corpse, job, errorOnFailed: errorOnFailed))
            {
                return false;
            }
            foreach (LocalTargetInfo source in sources)
            {
                if (!pawn.Reserve(source, job, errorOnFailed: errorOnFailed))
                {
                    JobFailReason.Is("AyameICCT_KeyMissing".Translate(requiredCost));
                    return false;
                }
            }
            job.targetQueueB = sources;
            job.countQueue = counts;
            return true;
        }

        protected override IEnumerable<Toil> MakeNewToils()
        {
            this.FailOn(() => !TargetAvailable());
            AddFinishAction(_ => pawn.inventory.UnloadEverything = true);

            Toil gotoCorpse = Toils_Goto.GotoThing(TargetIndex.A, PathEndMode.Touch);
            Toil extract = Toils_JobTransforms.ExtractNextTargetFromQueue(TargetIndex.B);
            Toil gotoSource = Toils_Goto.GotoThing(TargetIndex.B, PathEndMode.ClosestTouch, canGotoSpawnedParent: true)
                .FailOnForbidden(TargetIndex.B);
            Toil pick = Toils_General.Do(PickUpKeys);
            Toil gotoStaging = Toils_Goto.GotoThing(TargetIndex.A, PathEndMode.Touch);
            Toil place = Toils_General.Do(PlaceCarriedKeys);
            Toil work = Toils_General.Wait(600, TargetIndex.A);
            work.WithProgressBarToilDelay(TargetIndex.A);
            work.FailOnCannotTouch(TargetIndex.A, PathEndMode.Touch);
            Toil verify = Toils_General.Do(VerifyReady);
            Toil reprogram = Toils_General.Do(Reprogram);

            // Fixed toil shape: saved curToilIndex and both collection modes share these indices.
            Toil decide = Toils_Jump.JumpIf(gotoCorpse, () => job.GetTargetQueue(TargetIndex.B).NullOrEmpty()
                && pawn.carryTracker.CarriedThing == null);
            Toil inventoryContinue = Toils_Jump.JumpIf(decide, () => !batchMode);
            Toil batchContinue = Toils_Jump.Jump(decide);
            yield return decide;
            yield return extract;
            yield return gotoSource;
            yield return pick;
            yield return inventoryContinue;
            yield return gotoStaging;
            yield return place;
            yield return batchContinue;
            yield return gotoCorpse;
            yield return verify;
            yield return work;
            yield return reprogram;
        }

        private bool TargetAvailable()
        {
            return Corpse is { Spawned: true } corpse && corpse.Map == pawn.Map && !corpse.IsForbidden(pawn)
                && corpse.InnerPawn is { Dead: true } mech && mech.RaceProps.IsMechanoid
                && mech.Faction != Faction.OfPlayer;
        }

        private bool SourceAvailable(Thing source)
        {
            return source != null && !source.Destroyed && source.def == keyDef && source.stackCount > 0
                && source.SpawnedOrAnyParentSpawned && source.MapHeld == pawn.Map && source.holdingOwner != null
                && source.SpawnedParentOrMe is not Pawn && !source.IsForbidden(pawn)
                && (source.ParentHolder is not IHaulSource holder || holder.HaulSourceEnabled);
        }

        private bool HasCapacity(double addedMass, int stacks)
        {
            return stacks <= InventoryStackLimit - pawn.inventory.innerContainer.Count
                && double.IsFinite(addedMass) && addedMass >= 0
                && (addedMass == 0 || addedMass <= MassUtility.FreeSpace(pawn));
        }

        private void PickUpKeys()
        {
            Thing source = job.targetB.Thing;
            if (!SourceAvailable(source) || job.count <= 0 || source.stackCount < job.count
                || !pawn.Map.reservationManager.ReservedBy(source, pawn, job)
                || !pawn.CanReachImmediate(source.SpawnedParentOrMe, PathEndMode.ClosestTouch))
            {
                Stop("AyameICCT_KeyInterrupted");
                return;
            }
            if (!batchMode)
            {
                float mass = source.GetStatValue(StatDefOf.Mass);
                if (float.IsFinite(mass) && mass >= 0f && HasCapacity((double)job.count * mass, 1))
                {
                    ThingOwner originalOwner = source.holdingOwner;
                    IntVec3 originalPosition = source.PositionHeld;
                    Thing part = source.SplitOff(job.count);
                    // Native TakeToInventory ignores TryAdd failure and can silently short-take; this step is synchronous.
                    if (pawn.inventory.innerContainer.TryAdd(part, canMergeWithExistingStacks: false))
                    {
                        return;
                    }
                    if (part != source)
                    {
                        source.TryAbsorbStack(part, respectStackLimit: false);
                    }
                    else if (originalOwner.Owner is Map map)
                    {
                        GenSpawn.Spawn(part, originalPosition, map);
                    }
                    else
                    {
                        // A container normally accepts its own stack back; if a modded holder
                        // refuses, leave the keys recoverable on the floor instead of losing them.
                        if (!originalOwner.TryAdd(part, canMergeWithExistingStacks: false)
                            && originalPosition.InBounds(pawn.Map))
                        {
                            GenSpawn.Spawn(part, originalPosition, pawn.Map);
                        }
                    }
                }
                // Inventory was full, changed after planning, or refused the transfer:
                // the same source is carried by hand from here on.
                batchMode = true;
            }
            StartCarry(source);
        }

        // Mirrors Toils_Haul.StartCarryThing(putRemainderInQueue:true,
        // failIfStackCountLessThanJobCount:true, reserve:false, canTakeFromInventory:true)
        // without depending on a specific toil index. Native carry space is independent of inventory mass.
        private void StartCarry(Thing source)
        {
            if (!SourceAvailable(source) || job.count <= 0 || source.stackCount < job.count
                || !pawn.Map.reservationManager.ReservedBy(source, pawn, job)
                || !pawn.CanReachImmediate(source.SpawnedParentOrMe, PathEndMode.ClosestTouch))
            {
                Stop("AyameICCT_KeyInterrupted");
                return;
            }
            int space = pawn.carryTracker.AvailableStackSpace(keyDef);
            if (space <= 0)
            {
                Stop("AyameICCT_KeyCapacity");
                return;
            }
            int take = Math.Min(job.count, Math.Min(space, source.stackCount));
            int sourceCount = source.stackCount;
            int taken = pawn.carryTracker.TryStartCarry(source, take, reserve: false);
            if (taken <= 0)
            {
                Stop("AyameICCT_KeyCapacity");
                return;
            }
            if (taken < sourceCount)
            {
                int remainder = job.count - taken;
                if (remainder > 0)
                {
                    job.GetTargetQueue(TargetIndex.B).Insert(0, source);
                    job.countQueue ??= new List<int>();
                    job.countQueue.Insert(0, remainder);
                }
                else if (pawn.Map.reservationManager.ReservedBy(source, pawn, job))
                {
                    pawn.Map.reservationManager.Release(source, pawn, job);
                }
            }
        }

        private void PlaceCarriedKeys()
        {
            Thing carried = pawn.carryTracker.CarriedThing;
            Corpse corpse = Corpse;
            if (!batchMode || carried == null || carried.def != keyDef || carried.stackCount <= 0
                || !TargetAvailable() || corpse == null)
            {
                Stop("AyameICCT_KeyInterrupted");
                return;
            }
            Map map = corpse.Map;
            int expected = carried.stackCount;
            int cellCount = GenRadial.NumCellsInRadius(StagingRadius);
            for (int i = 0; i < cellCount; i++)
            {
                IntVec3 cell = corpse.Position + GenRadial.RadialPattern[i];
                if (!cell.InBounds(map) || !cell.Walkable(map))
                {
                    continue;
                }
                if (CellHoldsKeys(cell, map)
                    || cell.GetItemCount(map) >= cell.GetMaxItemsAllowedInCell(map))
                {
                    continue;
                }
                if (!GenSpawn.CanSpawnAt(keyDef, cell, map))
                {
                    continue;
                }
                if (!pawn.CanReserve(cell))
                {
                    continue; // another pawn already reserved this drop cell
                }
                if (!map.reachability.CanReach(corpse.Position, cell, PathEndMode.OnCell, TraverseMode.PassDoors, Danger.Deadly))
                {
                    continue;
                }

                Thing placed = null;
                int added = 0;
                bool dropped = pawn.carryTracker.TryDropCarriedThing(cell, ThingPlaceMode.Direct,
                    out Thing resulting, (thing, count) => { placed = thing; added = count; });
                if (!dropped)
                {
                    continue;
                }
                if (placed == null)
                {
                    // Direct placement into an empty cell returns the carried thing itself.
                    if (!ReferenceEquals(resulting, carried))
                    {
                        Stop("AyameICCT_KeyInterrupted");
                        return;
                    }
                    placed = resulting;
                    added = expected;
                }
                if (placed == null || placed.def != keyDef || added <= 0 || added > placed.stackCount
                    || !ReferenceEquals(placed, carried) || placed.stackCount != expected)
                {
                    Stop("AyameICCT_KeyInterrupted");
                    return;
                }
                if (!pawn.CanReserve(placed))
                {
                    Stop("AyameICCT_KeyInterrupted");
                    return;
                }
                pawn.Reserve(placed, job);
                HaulAIUtility.UpdateJobWithPlacedThings(job, placed, added);
                return;
            }
            Stop("AyameICCT_KeyNoStagingSpace");
        }

        private bool CellHoldsKeys(IntVec3 cell, Map map)
        {
            foreach (Thing thing in cell.GetThingList(map))
            {
                if (thing.def == keyDef || thing is IThingHolder holder && ThingHoldsKeys(holder))
                {
                    return true;
                }
            }
            return false;
        }

        private bool ThingHoldsKeys(IThingHolder holder)
        {
            ThingOwner owner = holder.GetDirectlyHeldThings();
            if (owner == null)
            {
                return false;
            }
            foreach (Thing thing in owner)
            {
                if (thing.def == keyDef || thing is IThingHolder nested && ThingHoldsKeys(nested))
                {
                    return true;
                }
            }
            return false;
        }

        private bool StagedKeysValid(bool requireReserved)
        {
            if (job.placedThings == null)
            {
                return true;
            }
            Corpse corpse = Corpse;
            if (corpse == null)
            {
                return false;
            }
            float radiusSquared = StagingRadius * StagingRadius;
            foreach (ThingCountClass entry in job.placedThings)
            {
                Thing thing = entry?.thing;
                if (thing == null || entry!.Count <= 0 || thing.Destroyed || !thing.Spawned
                    || thing.MapHeld != pawn.Map || thing.def != keyDef || entry.Count > thing.stackCount)
                {
                    return false;
                }
                if ((thing.PositionHeld - corpse.Position).LengthHorizontalSquared > radiusSquared)
                {
                    return false;
                }
                if (requireReserved && !pawn.Map.reservationManager.ReservedBy(thing, pawn, job))
                {
                    return false;
                }
            }
            return true;
        }

        private int CountStagedKeys(int limit)
        {
            int count = 0;
            if (job.placedThings == null)
            {
                return count;
            }
            foreach (ThingCountClass entry in job.placedThings)
            {
                if (entry?.thing != null)
                {
                    count += Math.Min(entry.Count, limit - count);
                    if (count == limit)
                    {
                        break;
                    }
                }
            }
            return count;
        }

        private int CountAvailableKeys(int limit)
        {
            int count = ReprogrammingKeyUtility.CountInventory(pawn, keyDef, limit);
            return count == limit ? count : count + CountStagedKeys(limit - count);
        }

        private void VerifyReady()
        {
            if (requiredCost < 0 || keyDef == null || !TargetAvailable()
                || !job.GetTargetQueue(TargetIndex.B).NullOrEmpty()
                || pawn.carryTracker.CarriedThing != null
                || !StagedKeysValid(requireReserved: true)
                || CountAvailableKeys(requiredCost) < requiredCost)
            {
                Stop("AyameICCT_KeyInterrupted");
            }
        }

        private void Reprogram()
        {
            if (requiredCost < 0 || keyDef == null || !TargetAvailable()
                || !ReprogrammingKeyUtility.GetCost(Corpse, out int currentCost)
                || currentCost != requiredCost
                || !pawn.Map.reservationManager.ReservedBy(Corpse, pawn, job)
                || !pawn.CanReachImmediate(Corpse, PathEndMode.Touch)
                || !StagedKeysValid(requireReserved: true)
                || CountAvailableKeys(requiredCost) < requiredCost)
            {
                Stop("AyameICCT_KeyInterrupted");
                return;
            }
            Corpse.InnerPawn.SetFactionDirect(Faction.OfPlayer);
            ReprogrammingKeyUtility.EnsureName(Corpse.InnerPawn);
            int remaining = requiredCost;
            foreach (Thing key in pawn.inventory.innerContainer.ToList())
            {
                if (remaining <= 0)
                {
                    break;
                }
                if (key.def == keyDef)
                {
                    int take = Math.Min(remaining, key.stackCount);
                    key.SplitOff(take).Destroy();
                    remaining -= take;
                }
            }
            if (remaining > 0 && job.placedThings != null)
            {
                foreach (ThingCountClass entry in job.placedThings.ToList())
                {
                    if (remaining <= 0)
                    {
                        break;
                    }
                    Thing key = entry?.thing;
                    if (key == null || key.Destroyed || key.def != keyDef)
                    {
                        continue;
                    }
                    int take = Math.Min(remaining, Math.Min(entry!.Count, key.stackCount));
                    if (take > 0)
                    {
                        key.SplitOff(take).Destroy();
                        remaining -= take;
                    }
                }
            }
            // Payment is exact and all-or-nothing; the job no longer owns any staged leftover.
            job.placedThings = null;
            Messages.Message("AyameICCT_KeyCompleted".Translate(requiredCost, Corpse.InnerPawn.LabelShort),
                Corpse, MessageTypeDefOf.PositiveEvent, historical: false);
        }

        private void Stop(string key)
        {
            Messages.Message(key.Translate(), pawn, MessageTypeDefOf.RejectInput, historical: false);
            EndJobWith(JobCondition.Incompletable);
        }
    }
}

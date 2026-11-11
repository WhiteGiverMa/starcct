using System.Collections.Generic;
using RimWorld;
using UnityEngine;
using Verse;
using Verse.AI;

namespace AyameICCT
{
    public sealed class Building_HoloSignboard : Building
    {
        public override IEnumerable<Gizmo> GetGizmos()
        {
            foreach (Gizmo gizmo in base.GetGizmos())
            {
                yield return gizmo;
            }
            if (Faction != Faction.OfPlayer)
            {
                yield break;
            }
            Command_Action contact = new Command_Action
            {
                defaultLabel = "AyameICCT_ContactRestaurant".Translate(),
                defaultDesc = "AyameICCT_HoloSignboardContactDesc".Translate(),
                icon = ContentFinder<Texture2D>.Get(def.uiIconPath, false)
                    ?? BaseContent.BadTex,
                action = () =>
                {
                    if (ShopPurchase.IsContextValid(this, null))
                    {
                        Find.WindowStack.Add(new CommsConsoleShop.Dialog_ShopMerchant(this, null));
                    }
                }
            };
            string failure = RestaurantTerminal.FailureReason(this);
            if (failure != null)
            {
                contact.Disable(failure);
            }
            yield return contact;
        }

        public override IEnumerable<FloatMenuOption> GetFloatMenuOptions(Pawn myPawn)
        {
            return CommsConsoleShop.AppendContactOption(base.GetFloatMenuOptions(myPawn), this, myPawn);
        }
    }

    internal static class RestaurantTerminal
    {
        internal static PathEndMode ApproachMode(Building terminal)
        {
            return terminal.def.hasInteractionCell ? PathEndMode.InteractionCell : PathEndMode.Touch;
        }

        internal static bool IsAtTerminal(Building terminal, Pawn actor)
        {
            return terminal.def.hasInteractionCell
                ? terminal.InteractionCell.InBounds(terminal.Map) && actor.Position == terminal.InteractionCell
                : actor.CanReachImmediate(terminal, PathEndMode.Touch);
        }

        internal static string FailureReason(Building terminal)
        {
            if (terminal == null || !terminal.Spawned || terminal.Map == null
                || terminal.Faction != Faction.OfPlayer)
            {
                return "AyameICCT_ShopUnavailable".Translate();
            }
            if (terminal.Map.gameConditionManager.ElectricityDisabled(terminal.Map))
            {
                return "CannotUseSolarFlare".Translate();
            }
            return IsIlluminated(terminal) ? null : "CannotUseNoPower".Translate();
        }

        internal static bool IsIlluminated(ThingWithComps terminal)
        {
            if (terminal == null || !terminal.Spawned || terminal.Map == null
                || terminal.Map.gameConditionManager.ElectricityDisabled(terminal.Map))
            {
                return false;
            }
            CompPowerTrader power = terminal.GetComp<CompPowerTrader>();
            CompFlickable flick = terminal.GetComp<CompFlickable>();
            return (power == null || power.PowerOn) && (flick == null || flick.SwitchIsOn);
        }

        internal static bool CanUseNow(Building terminal)
        {
            return (terminal is Building_CommsConsole || terminal is Building_HoloSignboard)
                && IsIlluminated(terminal);
        }
    }

    public sealed class CompProperties_HoloSignboard : CompProperties
    {
        public GraphicData graphicDataExtra;

        public CompProperties_HoloSignboard()
        {
            compClass = typeof(CompHoloSignboard);
        }
    }

    public sealed class CompHoloSignboard : ThingComp
    {
        public override void PostDraw()
        {
            base.PostDraw();
            if (!RestaurantTerminal.IsIlluminated(parent))
            {
                return;
            }
            GraphicData data = ((CompProperties_HoloSignboard)props).graphicDataExtra;
            Graphic graphic = data.Graphic;
            Vector3 drawPos = HologramDrawPos(parent, data);
            Graphics.DrawMesh(graphic.MeshAt(parent.Rotation),
                drawPos,
                // Match Graphic.DrawWorker's rotation contract. Four supplied
                // directional textures already bake their rotation (identity);
                // a graphic using fallback directions may need a quaternion.
                graphic.QuatFromRot(parent.Rotation), graphic.MatAt(parent.Rotation, parent), 0);
        }

        internal static Vector3 HologramDrawPos(Thing parent, GraphicData data)
        {
            Vector3 drawPos = parent.DrawPos + data.DrawOffsetForRot(parent.Rotation);
            // The projection extends into the wall's cell; keep it above wall tops as well as its base.
            drawPos.y = Mathf.Max(drawPos.y, Altitudes.AltitudeFor(AltitudeLayer.MoteOverhead));
            return drawPos;
        }
    }

    public sealed class ThoughtWorker_SawStrangeSignboard : ThoughtWorker
    {
        private const float ObservationRadius = 10f;
        private static readonly string[] SignDefNames = { "AyameICCT_HoloSignboard", "AyameICCT_WallHoloSignboard" };

        protected override ThoughtState CurrentStateInternal(Pawn p)
        {
            if (p == null || !p.Spawned || p.Map == null || !p.Awake()
                || p.story?.traits?.HasTrait(DefDatabase<TraitDef>.GetNamed("TorturedArtist", false)) != true
                || PawnUtility.IsBiologicallyOrArtificiallyBlind(p)
                || !p.health.capacities.CapableOf(PawnCapacityDefOf.Sight))
            {
                return ThoughtState.Inactive;
            }
            foreach (string defName in SignDefNames)
            {
                ThingDef signDef = DefDatabase<ThingDef>.GetNamed(defName, false);
                if (signDef == null)
                {
                    continue;
                }
                foreach (Thing thing in p.Map.listerThings.ThingsOfDef(signDef))
                {
                    if (thing is Building_HoloSignboard sign && RestaurantTerminal.IsIlluminated(sign)
                        && p.Position.InHorDistOf(sign.Position, ObservationRadius)
                        && GenSight.LineOfSight(p.Position, sign.Position, p.Map, skipFirstCell: true))
                    {
                        return ThoughtState.ActiveAtStage(0);
                    }
                }
            }
            return ThoughtState.Inactive;
        }
    }
}

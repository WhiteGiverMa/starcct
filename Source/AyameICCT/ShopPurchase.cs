using System;
using System.Collections.Generic;
using RimWorld;
using Verse;

namespace AyameICCT
{
    internal enum ShopPurchaseFailure
    {
        None,
        InvalidQuantity,
        InvalidPrice,
        InsufficientSilver,
        NoDropSpot,
        Unavailable,
        MissingKey
    }

    internal readonly struct ShopQuote
    {
        internal readonly int Granules;
        internal readonly int Sheets;
        internal readonly int Keys;
        internal readonly int Total;
        internal readonly decimal GranuleUnitPrice;
        internal readonly decimal SheetUnitPrice;
        internal readonly decimal KeyUnitPrice;

        internal ShopQuote(int granules, int sheets, int keys, int total,
            decimal granuleUnitPrice, decimal sheetUnitPrice, decimal keyUnitPrice)
        {
            Granules = granules;
            Sheets = sheets;
            Keys = keys;
            Total = total;
            GranuleUnitPrice = granuleUnitPrice;
            SheetUnitPrice = sheetUnitPrice;
            KeyUnitPrice = keyUnitPrice;
        }

        internal bool HasGoods => Granules > 0 || Sheets > 0 || Keys > 0;
    }

    internal static class ShopPurchase
    {
        internal const string GranuleDefName = "AyameICCT_PlasticGranule";
        internal const string SheetDefName = "AyameICCT_PlasticSheet";
        internal const string KeyDefName = "AyameICCT_ReprogrammingKey";
        internal const int PlasticMin = 0;
        internal const int PlasticMax = 20000;
        internal const int PlasticStep = 500;
        internal const int KeyMin = 1;
        internal const int KeyMax = 10;
        internal const int KeyStep = 1;
        private const int PodOpenDelay = 110;

        internal static bool KeyOfferAvailable
        {
            get
            {
                if (!ModsConfig.BiotechActive)
                {
                    return false;
                }
                return DefDatabase<ThingDef>.GetNamed(KeyDefName, false) != null;
            }
        }

        internal static ThingDef GranuleDef => DefDatabase<ThingDef>.GetNamed(GranuleDefName, false);

        internal static ThingDef SheetDef => DefDatabase<ThingDef>.GetNamed(SheetDefName, false);

        internal static ThingDef KeyDef => DefDatabase<ThingDef>.GetNamed(KeyDefName, false);

        internal static bool ValidPlasticQuantity(int amount)
        {
            return amount >= PlasticMin && amount <= PlasticMax && amount % PlasticStep == 0;
        }

        internal static bool ValidKeyQuantity(int amount)
        {
            return amount >= KeyMin && amount <= KeyMax;
        }

        internal static bool TryQuote(int granules, int sheets, int keys, out ShopQuote quote,
            out ShopPurchaseFailure failure)
        {
            quote = default;
            if (!ValidPlasticQuantity(granules) || !ValidPlasticQuantity(sheets)
                || keys < 0 || keys > KeyMax)
            {
                failure = ShopPurchaseFailure.InvalidQuantity;
                return false;
            }

            decimal granulePrice = 0m;
            decimal sheetPrice = 0m;
            if (granules > 0)
            {
                if (!TryUnitPrice(GranuleDef, out granulePrice))
                {
                    failure = ShopPurchaseFailure.InvalidPrice;
                    return false;
                }
            }
            if (sheets > 0)
            {
                if (!TryUnitPrice(SheetDef, out sheetPrice))
                {
                    failure = ShopPurchaseFailure.InvalidPrice;
                    return false;
                }
            }

            decimal keyPrice = 0m;
            if (keys > 0)
            {
                ThingDef keyDef = KeyDef;
                if (!KeyOfferAvailable || keyDef == null)
                {
                    failure = ShopPurchaseFailure.MissingKey;
                    return false;
                }
                if (!TryUnitPrice(keyDef, out keyPrice))
                {
                    failure = ShopPurchaseFailure.InvalidPrice;
                    return false;
                }
            }

            decimal raw;
            decimal rounded;
            try
            {
                raw = granules * granulePrice + sheets * sheetPrice + keys * keyPrice;
                rounded = decimal.Round(raw, 0, MidpointRounding.AwayFromZero);
            }
            catch (OverflowException)
            {
                failure = ShopPurchaseFailure.InvalidPrice;
                return false;
            }
            if (rounded > int.MaxValue || rounded < int.MinValue)
            {
                failure = ShopPurchaseFailure.InvalidPrice;
                return false;
            }
            int total = (int)rounded;
            bool hasGoods = granules > 0 || sheets > 0 || keys > 0;
            if (hasGoods && total < 1)
            {
                // A positive order must never become free through rounding.
                failure = ShopPurchaseFailure.InvalidPrice;
                return false;
            }

            quote = new ShopQuote(granules, sheets, keys, total, granulePrice, sheetPrice, keyPrice);
            failure = ShopPurchaseFailure.None;
            return true;
        }

        internal static bool IsContextValid(Building_CommsConsole console, Pawn actor)
        {
            if (console == null || actor == null || !console.Spawned || console.Map == null
                || !actor.Spawned || actor.Map != console.Map)
            {
                return false;
            }
            if (console.Faction != Faction.OfPlayer || console.IsForbidden(actor))
            {
                return false;
            }
            if (!console.CanUseCommsNow)
            {
                return false;
            }
            if (!actor.health.capacities.CapableOf(PawnCapacityDefOf.Talking))
            {
                return false;
            }
            IntVec3 interactionCell = console.InteractionCell;
            return interactionCell.InBounds(console.Map) && actor.Position == interactionCell;
        }

        internal static int CountHomeSilver(Map map)
        {
            if (map == null || ThingDefOf.Silver == null)
            {
                return 0;
            }
            long total = 0;
            foreach (Thing silver in map.listerThings.ThingsOfDef(ThingDefOf.Silver))
            {
                if (silver == null || silver.Destroyed || !silver.Spawned || silver.Map != map
                    || !map.areaManager.Home[silver.Position])
                {
                    continue;
                }
                total += silver.stackCount;
                if (total >= int.MaxValue)
                {
                    return int.MaxValue;
                }
            }
            return (int)total;
        }

        internal static bool TryPurchase(Building_CommsConsole console, Pawn actor,
            int granules, int sheets, int keys, out ShopPurchaseFailure failure, out int charged)
        {
            failure = ShopPurchaseFailure.None;
            charged = 0;

            if (!TryQuote(granules, sheets, keys, out ShopQuote quote, out failure))
            {
                return false;
            }
            if (!quote.HasGoods)
            {
                failure = ShopPurchaseFailure.InvalidQuantity;
                return false;
            }
            if (!IsContextValid(console, actor))
            {
                failure = ShopPurchaseFailure.Unavailable;
                return false;
            }

            Map map = console.Map;
            ThingDef granuleDef = granules > 0 ? GranuleDef : null;
            ThingDef sheetDef = sheets > 0 ? SheetDef : null;
            ThingDef keyDef = keys > 0 ? KeyDef : null;
            if ((granules > 0 && granuleDef == null) || (sheets > 0 && sheetDef == null)
                || (keys > 0 && keyDef == null))
            {
                failure = keys > 0 && keyDef == null
                    ? ShopPurchaseFailure.MissingKey
                    : ShopPurchaseFailure.InvalidPrice;
                return false;
            }

            ActiveTransporterInfo info = new ActiveTransporterInfo
            {
                openDelay = PodOpenDelay,
                leaveSlag = false
            };
            if ((granules > 0 && !TryPrepareGoods(info, granuleDef, granules))
                || (sheets > 0 && !TryPrepareGoods(info, sheetDef, sheets)))
            {
                info.innerContainer.ClearAndDestroyContents();
                failure = ShopPurchaseFailure.InvalidQuantity;
                return false;
            }
            if (keys > 0 && !TryPrepareGoods(info, keyDef, keys))
            {
                info.innerContainer.ClearAndDestroyContents();
                failure = keys > 0 ? ShopPurchaseFailure.MissingKey : ShopPurchaseFailure.InvalidQuantity;
                return false;
            }

            // The order is deliberately only quoted/reserved here; no map mutation
            // happens until delivery and the complete Home-silver plan are validated.
            IntVec3 spot = DropCellFinder.TradeDropSpot(map);
            if (!spot.IsValid || !spot.InBounds(map)
                || !DropCellFinder.IsGoodDropSpot(spot, map, allowFogged: false, canRoofPunch: false))
            {
                info.innerContainer.ClearAndDestroyContents();
                failure = ShopPurchaseFailure.NoDropSpot;
                return false;
            }

            if (!TryPlanSilver(map, quote.Total, out List<SilverTake> plan, out _))
            {
                info.innerContainer.ClearAndDestroyContents();
                failure = ShopPurchaseFailure.InsufficientSilver;
                return false;
            }

            // Recheck external state immediately before the first mutation.
            if (!IsContextValid(console, actor))
            {
                info.innerContainer.ClearAndDestroyContents();
                failure = ShopPurchaseFailure.Unavailable;
                return false;
            }
            if (!TryQuote(granules, sheets, keys, out ShopQuote rechecked, out failure))
            {
                info.innerContainer.ClearAndDestroyContents();
                return false;
            }
            if (rechecked.Total != quote.Total)
            {
                info.innerContainer.ClearAndDestroyContents();
                failure = ShopPurchaseFailure.InvalidPrice;
                return false;
            }

            DropPodUtility.MakeDropPodAt(spot, map, info, faction: null);
            foreach (SilverTake take in plan)
            {
                take.Thing.SplitOff(take.Count).Destroy();
            }
            charged = quote.Total;
            failure = ShopPurchaseFailure.None;
            return true;
        }

        private static bool TryPrepareGoods(ActiveTransporterInfo info, ThingDef def, int count)
        {
            if (count < 0)
            {
                return false;
            }
            if (count == 0)
            {
                return true;
            }
            if (def == null)
            {
                return false;
            }
            int stackLimit = def.stackLimit;
            if (stackLimit <= 0)
            {
                return false;
            }
            int remaining = count;
            while (remaining > 0)
            {
                int take = Math.Min(remaining, stackLimit);
                Thing thing = ThingMaker.MakeThing(def);
                thing.stackCount = take;
                if (!info.innerContainer.TryAdd(thing, canMergeWithExistingStacks: false))
                {
                    thing.Destroy();
                    return false;
                }
                remaining -= take;
            }
            return true;
        }

        private static bool TryUnitPrice(ThingDef def, out decimal price)
        {
            price = 0m;
            if (def == null)
            {
                return false;
            }
            float marketValue = def.GetStatValueAbstract(StatDefOf.MarketValue);
            if (!float.IsFinite(marketValue) || marketValue <= 0f)
            {
                return false;
            }
            try
            {
                price = (decimal)marketValue;
            }
            catch (OverflowException)
            {
                price = 0m;
                return false;
            }
            return price > 0m;
        }

        private static bool TryPlanSilver(Map map, int cost, out List<SilverTake> plan, out int available)
        {
            plan = new List<SilverTake>();
            available = 0;
            if (cost <= 0 || ThingDefOf.Silver == null)
            {
                return false;
            }
            foreach (Thing silver in map.listerThings.ThingsOfDef(ThingDefOf.Silver))
            {
                if (silver == null || silver.Destroyed || !silver.Spawned || silver.Map != map
                    || silver.stackCount <= 0 || !map.areaManager.Home[silver.Position])
                {
                    continue;
                }
                int take = Math.Min(cost - available, silver.stackCount);
                if (take > 0)
                {
                    plan.Add(new SilverTake(silver, take));
                    available += take;
                    if (available >= cost)
                    {
                        break;
                    }
                }
            }
            return available >= cost;
        }

        private readonly struct SilverTake
        {
            internal readonly Thing Thing;
            internal readonly int Count;

            internal SilverTake(Thing thing, int count)
            {
                Thing = thing;
                Count = count;
            }
        }
    }
}

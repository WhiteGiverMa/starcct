using System;
using System.Collections.Generic;
using RimWorld;
using UnityEngine;
using Verse;
using Verse.AI;

namespace AyameICCT
{
    internal static class CommsConsoleShop
    {
        internal const string ContactJobDefName = "AyameICCT_ContactRestaurant";

        internal static IEnumerable<FloatMenuOption> AppendContactOption(IEnumerable<FloatMenuOption> original,
            Building_CommsConsole console, Pawn pawn)
        {
            if (original != null)
            {
                foreach (FloatMenuOption option in original)
                {
                    yield return option;
                }
            }

            FloatMenuOption contact = MakeContactOption(console, pawn);
            if (contact != null)
            {
                yield return contact;
            }
        }

        // ponytail: the shop is a direct service on the console, not a hidden faction or
        // ICommunicable singleton. If it ever needs persistent relations/trade state,
        // that state belongs in a real faction instead of a menu-only shim.
        private static FloatMenuOption MakeContactOption(Building_CommsConsole console, Pawn pawn)
        {
            if (console == null || pawn == null)
            {
                return null;
            }

            string failure = FailureReason(console, pawn);
            if (failure != null)
            {
                return new FloatMenuOption("AyameICCT_ContactRestaurant".Translate(), null);
            }
            return new FloatMenuOption("AyameICCT_ContactRestaurant".Translate(), () => OrderContact(console, pawn));
        }

        private static string FailureReason(Building_CommsConsole console, Pawn pawn)
        {
            if (!console.Spawned || console.Map == null || console.Map != pawn.Map || !pawn.Spawned)
            {
                return "CannotUseNoPath".Translate();
            }
            if (console.Faction != Faction.OfPlayer || console.IsForbidden(pawn))
            {
                return "AyameICCT_ShopUnavailable".Translate();
            }
            if (!pawn.CanReach(console, PathEndMode.InteractionCell, Danger.Some))
            {
                return "CannotUseNoPath".Translate();
            }
            if (console.Map.gameConditionManager.ElectricityDisabled(console.Map))
            {
                return "CannotUseSolarFlare".Translate();
            }
            CompPowerTrader power = console.GetComp<CompPowerTrader>();
            if (power != null && !power.PowerOn)
            {
                return "CannotUseNoPower".Translate();
            }
            if (!pawn.health.capacities.CapableOf(PawnCapacityDefOf.Talking))
            {
                return "CannotUseReason".Translate("IncapableOfCapacity".Translate(
                    PawnCapacityDefOf.Talking.label, pawn.Named("PAWN")));
            }
            if (!console.CanUseCommsNow || !console.InteractionCell.InBounds(console.Map))
            {
                return "AyameICCT_ShopUnavailable".Translate();
            }
            return null;
        }

        private static void OrderContact(Building_CommsConsole console, Pawn pawn)
        {
            JobDef jobDef = DefDatabase<JobDef>.GetNamed(ContactJobDefName, false);
            if (jobDef == null)
            {
                Messages.Message("AyameICCT_ShopUnavailable".Translate(), pawn, MessageTypeDefOf.RejectInput, historical: false);
                return;
            }
            Job job = JobMaker.MakeJob(jobDef, console);
            pawn.jobs.TryTakeOrderedJob(job, JobTag.Misc);
        }

        private static string FailureMessage(ShopPurchaseFailure failure, int required)
        {
            switch (failure)
            {
                case ShopPurchaseFailure.InvalidQuantity:
                    return "AyameICCT_ShopInvalidQuantity".Translate();
                case ShopPurchaseFailure.InvalidPrice:
                    return "AyameICCT_ShopInvalidPrice".Translate();
                case ShopPurchaseFailure.InsufficientSilver:
                    return "AyameICCT_ShopNotEnoughSilver".Translate(required);
                case ShopPurchaseFailure.NoDropSpot:
                    return "AyameICCT_ShopNoDropSpot".Translate();
                case ShopPurchaseFailure.MissingKey:
                    return "AyameICCT_ShopMissingKey".Translate();
                case ShopPurchaseFailure.Unavailable:
                    return "AyameICCT_ShopUnavailable".Translate();
                default:
                    return "AyameICCT_ShopInvalidQuantity".Translate();
            }
        }

        private enum ShopView
        {
            Main,
            Plastics,
            Keys
        }

        internal sealed class Dialog_ShopMerchant : Window
        {
            private readonly Building_CommsConsole console;
            private readonly Pawn actor;
            private ShopView view;
            private float granuleSlider;
            private float sheetSlider;
            private float keySlider = ShopPurchase.KeyMin;
            private bool purchaseStarted;

            internal Dialog_ShopMerchant(Building_CommsConsole console, Pawn actor)
            {
                this.console = console;
                this.actor = actor;
                forcePause = true;
                closeOnAccept = false;
                closeOnCancel = true;
                doCloseX = true;
                absorbInputAroundWindow = true;
            }

            public override Vector2 InitialSize => new Vector2(620f, 400f);

            public override void DoWindowContents(Rect inRect)
            {
                if (console == null || actor == null)
                {
                    Close();
                    return;
                }

                if (view == ShopView.Main)
                {
                    DrawMain(inRect);
                }
                else if (view == ShopView.Plastics)
                {
                    DrawPlastics(inRect);
                }
                else
                {
                    DrawKeys(inRect);
                }
            }

            private void DrawMain(Rect inRect)
            {
                Text.Font = GameFont.Medium;
                Widgets.Label(new Rect(0f, 0f, inRect.width, 34f), "AyameICCT_ShopTitle".Translate());
                Text.Font = GameFont.Small;

                float y = 44f;
                Widgets.Label(new Rect(0f, y, inRect.width, 58f), "AyameICCT_ShopDelivery".Translate());
                y += 66f;
                Widgets.Label(new Rect(0f, y, inRect.width, 24f),
                    "AyameICCT_ShopSilver".Translate(ShopPurchase.CountHomeSilver(console.Map)));

                y += 36f;
                float width = (inRect.width - 12f) / 2f;
                if (Widgets.ButtonText(new Rect(0f, y, width, 40f), "AyameICCT_ShopPlastic".Translate()))
                {
                    view = ShopView.Plastics;
                }
                bool keysAvailable = ShopPurchase.KeyOfferAvailable;
                if (Widgets.ButtonText(new Rect(width + 12f, y, width, 40f),
                        "AyameICCT_ShopKeys".Translate(), active: keysAvailable) && keysAvailable)
                {
                    view = ShopView.Keys;
                }
                if (!keysAvailable)
                {
                    Widgets.Label(new Rect(width + 12f, y + 44f, width, 24f),
                        "AyameICCT_ShopMissingKey".Translate());
                }

                DrawCloseButton(inRect);
            }

            private void DrawPlastics(Rect inRect)
            {
                DrawQuantityTitle(inRect);
                float y = 44f;
                int granules = PlasticGranules();
                int sheets = PlasticSheets();
                ShopPurchase.TryQuote(granules, sheets, 0, out ShopQuote quote, out ShopPurchaseFailure failure);

                Widgets.Label(new Rect(0f, y, inRect.width, 24f),
                    ShopPurchase.GranuleDef.LabelCap + "  " + granules.ToString());
                float granuleValue = granuleSlider;
                Widgets.HorizontalSlider(new Rect(0f, y + 24f, inRect.width, 22f),
                    ref granuleValue, new FloatRange(ShopPurchase.PlasticMin, ShopPurchase.PlasticMax), null,
                    ShopPurchase.PlasticStep);
                granuleSlider = granuleValue;
                y += 58f;

                Widgets.Label(new Rect(0f, y, inRect.width, 24f),
                    ShopPurchase.SheetDef.LabelCap + "  " + sheets.ToString());
                float sheetValue = sheetSlider;
                Widgets.HorizontalSlider(new Rect(0f, y + 24f, inRect.width, 22f),
                    ref sheetValue, new FloatRange(ShopPurchase.PlasticMin, ShopPurchase.PlasticMax), null,
                    ShopPurchase.PlasticStep);
                sheetSlider = sheetValue;
                y += 58f;

                Widgets.Label(new Rect(0f, y, inRect.width, 24f),
                    "AyameICCT_ShopUnitPrice".Translate(FormatPrice(quote.GranuleUnitPrice)));
                Widgets.Label(new Rect(0f, y + 24f, inRect.width, 24f),
                    "AyameICCT_ShopUnitPrice".Translate(FormatPrice(quote.SheetUnitPrice)));
                y += 56f;

                DrawTotals(inRect, y, quote.Total, failure);
                DrawPurchaseButtons(inRect, BuyPlastic, failure, quote.Total);
            }

            private void DrawKeys(Rect inRect)
            {
                DrawQuantityTitle(inRect);
                float y = 44f;
                int keys = KeyCount();
                ShopPurchase.TryQuote(0, 0, keys, out ShopQuote quote, out ShopPurchaseFailure failure);

                Widgets.Label(new Rect(0f, y, inRect.width, 24f),
                    ShopPurchase.KeyDef.LabelCap + "  " + keys.ToString());
                float keyValue = keySlider;
                Widgets.HorizontalSlider(new Rect(0f, y + 24f, inRect.width, 22f),
                    ref keyValue, new FloatRange(ShopPurchase.KeyMin, ShopPurchase.KeyMax), null,
                    ShopPurchase.KeyStep);
                keySlider = keyValue;
                y += 58f;

                Widgets.Label(new Rect(0f, y, inRect.width, 24f),
                    "AyameICCT_ShopUnitPrice".Translate(FormatPrice(quote.KeyUnitPrice)));
                y += 32f;

                DrawTotals(inRect, y, quote.Total, failure);
                DrawPurchaseButtons(inRect, BuyKeys, failure, quote.Total);
            }

            private void DrawQuantityTitle(Rect inRect)
            {
                Text.Font = GameFont.Medium;
                Widgets.Label(new Rect(0f, 0f, inRect.width, 34f), "AyameICCT_ShopQuantity".Translate());
                Text.Font = GameFont.Small;
                if (Widgets.ButtonText(new Rect(0f, inRect.height - 40f, 120f, 36f), "Back".Translate()))
                {
                    view = ShopView.Main;
                }
            }

            private void DrawTotals(Rect inRect, float y, int total, ShopPurchaseFailure failure)
            {
                Widgets.Label(new Rect(0f, y, inRect.width, 24f), "AyameICCT_ShopTotal".Translate(total));
                Widgets.Label(new Rect(0f, y + 24f, inRect.width, 24f),
                    "AyameICCT_ShopSilver".Translate(ShopPurchase.CountHomeSilver(console.Map)));
                if (failure == ShopPurchaseFailure.InvalidPrice)
                {
                    Widgets.Label(new Rect(0f, y + 48f, inRect.width, 24f),
                        "AyameICCT_ShopInvalidPrice".Translate());
                }
            }

            private void DrawPurchaseButtons(Rect inRect, Action buy, ShopPurchaseFailure failure, int total)
            {
                bool canBuy = CanPurchase(failure, total);
                float y = inRect.height - 40f;
                if (Widgets.ButtonText(new Rect(inRect.width - 300f, y, 140f, 36f),
                        "AyameICCT_ShopBuy".Translate(), active: canBuy) && canBuy)
                {
                    buy();
                }
                if (Widgets.ButtonText(new Rect(inRect.width - 148f, y, 140f, 36f),
                        "AyameICCT_ShopClose".Translate()))
                {
                    Close();
                }
            }

            private void DrawCloseButton(Rect inRect)
            {
                if (Widgets.ButtonText(new Rect(inRect.width - 148f, inRect.height - 40f, 140f, 36f),
                        "AyameICCT_ShopClose".Translate()))
                {
                    Close();
                }
            }

            private bool CanPurchase(ShopPurchaseFailure quoteFailure, int total)
            {
                if (purchaseStarted || quoteFailure != ShopPurchaseFailure.None)
                {
                    return false;
                }
                if (!ShopPurchase.IsContextValid(console, actor))
                {
                    return false;
                }
                return total > 0 && ShopPurchase.CountHomeSilver(console.Map) >= total;
            }

            private int PlasticGranules()
            {
                return Mathf.Clamp(Mathf.RoundToInt(granuleSlider / ShopPurchase.PlasticStep)
                    * ShopPurchase.PlasticStep, ShopPurchase.PlasticMin, ShopPurchase.PlasticMax);
            }

            private int PlasticSheets()
            {
                return Mathf.Clamp(Mathf.RoundToInt(sheetSlider / ShopPurchase.PlasticStep)
                    * ShopPurchase.PlasticStep, ShopPurchase.PlasticMin, ShopPurchase.PlasticMax);
            }

            private int KeyCount()
            {
                return Mathf.Clamp(Mathf.RoundToInt(keySlider), ShopPurchase.KeyMin, ShopPurchase.KeyMax);
            }

            private void BuyPlastic()
            {
                TryBuy(PlasticGranules(), PlasticSheets(), 0);
            }

            private void BuyKeys()
            {
                TryBuy(0, 0, KeyCount());
            }

            private void TryBuy(int granules, int sheets, int keys)
            {
                if (purchaseStarted)
                {
                    return;
                }
                purchaseStarted = true;
                ShopPurchase.TryQuote(granules, sheets, keys, out ShopQuote quote, out _);
                bool success = ShopPurchase.TryPurchase(console, actor, granules, sheets, keys,
                    out ShopPurchaseFailure failure, out int charged);
                if (success)
                {
                    Messages.Message("AyameICCT_ShopPurchased".Translate(charged), actor,
                        MessageTypeDefOf.PositiveEvent, historical: false);
                    Close();
                    return;
                }
                // Every non-success return is guaranteed to precede the first map mutation.
                purchaseStarted = false;
                Messages.Message(FailureMessage(failure, quote.Total), actor,
                    MessageTypeDefOf.RejectInput, historical: false);
            }

            private static string FormatPrice(decimal price)
            {
                return price.ToString(System.Globalization.CultureInfo.InvariantCulture);
            }
        }
    }
}

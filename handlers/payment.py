import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from database import add_transaction, set_premium, complete_transaction, is_premium
from config import (
    STARS_PRICE_1MONTH, STARS_PRICE_3MONTHS, STARS_PRICE_6MONTHS, STARS_PRICE_1YEAR,
    TON_PRICE_1MONTH,   TON_PRICE_3MONTHS,   TON_PRICE_6MONTHS,   TON_PRICE_1YEAR,
    USDT_PRICE_1MONTH,  USDT_PRICE_3MONTHS,  USDT_PRICE_6MONTHS,  USDT_PRICE_1YEAR,
    TON_WALLET, USDT_WALLET, ADMIN_IDS,
)

logger = logging.getLogger(__name__)

# ⬇️ Mets ici le @username de ton bot support
SUPPORT_BOT_USERNAME = "alphabot_support"

PLANS = {
    "1month":  {"days": 30,    "label": "1 mois",   "stars": STARS_PRICE_1MONTH,  "ton": TON_PRICE_1MONTH,  "usdt": USDT_PRICE_1MONTH},
    "3months": {"days": 90,    "label": "3 mois",   "stars": STARS_PRICE_3MONTHS, "ton": TON_PRICE_3MONTHS, "usdt": USDT_PRICE_3MONTHS},
    "6months": {"days": 180,   "label": "6 mois",   "stars": STARS_PRICE_6MONTHS, "ton": TON_PRICE_6MONTHS, "usdt": USDT_PRICE_6MONTHS},
    "1year":   {"days": 365,   "label": "1 an",     "stars": STARS_PRICE_1YEAR,   "ton": TON_PRICE_1YEAR,   "usdt": USDT_PRICE_1YEAR},
    "lifetime":{"days": 99999, "label": "Illimité", "stars": None,                "ton": None,               "usdt": None},
}


# ─── Affichage des plans ──────────────────────────────────────────────────────

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = update.effective_user.id

    if query:
        await query.answer()
        send_fn = query.edit_message_text
    else:
        send_fn = update.message.reply_text

    premium  = is_premium(user_id)
    is_admin = user_id in ADMIN_IDS
    badge    = "✅ Tu es déjà *Premium* !\n\n" if premium else ""

    text = (
        f"⚡ *Alpha Convert — Plans Premium*\n\n"
        f"{badge}"
        "🎯 *Avantages Premium :*\n"
        "• Téléchargements illimités\n"
        "• Fichiers jusqu'à 500MB\n"
        "• Priorité de traitement\n"
        "• Toutes qualités disponibles\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *1 mois*  →  {STARS_PRICE_1MONTH}⭐  |  {TON_PRICE_1MONTH} TON  |  {USDT_PRICE_1MONTH}$\n"
        f"📦 *3 mois*  →  {STARS_PRICE_3MONTHS}⭐  |  {TON_PRICE_3MONTHS} TON  |  {USDT_PRICE_3MONTHS}$\n"
        f"🏆 *6 mois*  →  {STARS_PRICE_6MONTHS}⭐  |  {TON_PRICE_6MONTHS} TON  |  {USDT_PRICE_6MONTHS}$\n"
        f"👑 *1 an*    →  {STARS_PRICE_1YEAR}⭐  |  {TON_PRICE_1YEAR} TON  |  {USDT_PRICE_1YEAR}$\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💳 *Méthodes de paiement :*\n"
        "⭐ Telegram Stars\n"
        "💎 TON\n"
        "💵 USDT (TRC20 ou BEP20)\n"
    )

    keyboard = [
        [InlineKeyboardButton("📅 1 mois",  callback_data="plan_1month"),
         InlineKeyboardButton("📦 3 mois",  callback_data="plan_3months")],
        [InlineKeyboardButton("🏆 6 mois",  callback_data="plan_6months"),
         InlineKeyboardButton("👑 1 an",    callback_data="plan_1year")],
        [InlineKeyboardButton("⬅️ Retour",  callback_data="menu")],
    ]

    if is_admin:
        keyboard.insert(-1, [InlineKeyboardButton("♾️ Illimité (Admin)", callback_data="plan_lifetime")])

    await send_fn(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ─── Choix du plan → choix méthode de paiement ───────────────────────────────

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_key = query.data.replace("plan_", "")
    plan     = PLANS[plan_key]
    context.user_data["selected_plan"] = plan_key

    text = (
        f"💎 *Plan {plan['label']}*\n\n"
        f"⭐ Stars : *{plan['stars']}*\n"
        f"💎 TON : *{plan['ton']}*\n"
        f"💵 USDT : *{plan['usdt']}$*\n\n"
        "Choisis ta méthode de paiement :"
    )

    keyboard = [
        [InlineKeyboardButton(f"⭐ Payer {plan['stars']} Stars", callback_data=f"pay_stars_{plan_key}")],
        [InlineKeyboardButton(f"💎 Payer {plan['ton']} TON",     callback_data=f"pay_ton_{plan_key}")],
        [InlineKeyboardButton(f"💵 Payer {plan['usdt']}$ USDT",  callback_data=f"pay_usdt_{plan_key}")],
        [InlineKeyboardButton("⬅️ Retour aux plans",             callback_data="premium")],
    ]

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ─── Paiement Stars ───────────────────────────────────────────────────────────

async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_key = query.data.replace("pay_stars_", "")
    plan     = PLANS[plan_key]
    context.user_data["pending_stars_plan"] = plan_key

    await query.message.reply_invoice(
        title=       f"Alpha Convert — Premium {plan['label']}",
        description= f"Accès Premium {plan['label']} • Téléchargements illimités",
        payload=     f"premium_{plan_key}_{query.from_user.id}",
        currency=    "XTR",
        prices=      [LabeledPrice(f"Premium {plan['label']}", plan["stars"])],
    )


# ─── Pre-checkout Stars ───────────────────────────────────────────────────────

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


# ─── Paiement Stars confirmé ─────────────────────────────────────────────────

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload
    amount  = update.message.successful_payment.total_amount

    parts    = payload.split("_")
    plan_key = parts[1] if len(parts) > 1 else "1month"
    plan     = PLANS.get(plan_key, PLANS["1month"])
    until    = date.today() + timedelta(days=plan["days"])

    add_transaction(user_id, plan_key, "XTR", amount)
    set_premium(user_id, until)

    from handlers.menu import main_keyboard
    await update.message.reply_text(
        f"🎉 *Paiement confirmé !*\n\n"
        f"💎 Tu es maintenant *Premium* jusqu'au *{until.strftime('%d/%m/%Y')}*\n"
        f"🚀 Accès illimité activé !",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


# ─── Paiement TON → redirection support ──────────────────────────────────────

async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()

    plan_key = query.data.replace("pay_ton_", "")
    plan     = PLANS[plan_key]

    await query.edit_message_text(
        f"💎 *Paiement TON — {plan['label']}*\n\n"
        f"Pour payer *{plan['ton']} TON*, contacte notre support :\n\n"
        f"1️⃣ Clique sur le bouton ci-dessous pour ouvrir le support\n"
        f"2️⃣ Indique que tu veux payer *{plan['ton']} TON* pour le plan *{plan['label']}*\n"
        f"3️⃣ Notre équipe t'enverra l'adresse et activera ton accès après réception\n\n"
        f"⚠️ Ton identité reste anonyme.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Contacter le support", url=f"https://t.me/{SUPPORT_BOT_USERNAME}")],
            [InlineKeyboardButton("⬅️ Retour", callback_data=f"plan_{plan_key}")],
        ]),
    )


# ─── Paiement USDT → redirection support ────────────────────────────────────

async def buy_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()

    plan_key = query.data.replace("pay_usdt_", "")
    plan     = PLANS[plan_key]

    await query.edit_message_text(
        f"💵 *Paiement USDT — {plan['label']}*\n\n"
        f"Pour payer *{plan['usdt']}$ USDT*, contacte notre support :\n\n"
        f"1️⃣ Clique sur le bouton ci-dessous pour ouvrir le support\n"
        f"2️⃣ Indique que tu veux payer *{plan['usdt']}$ USDT* pour le plan *{plan['label']}*\n"
        f"3️⃣ Notre équipe t'enverra l'adresse et activera ton accès après réception\n\n"
        f"📌 *Réseaux acceptés :* TRC20 ou BEP20\n\n"
        f"⚠️ Ton identité reste anonyme.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Contacter le support", url=f"https://t.me/{SUPPORT_BOT_USERNAME}")],
            [InlineKeyboardButton("⬅️ Retour", callback_data=f"plan_{plan_key}")],
        ]),
    )


# ─── Ces fonctions ne sont plus utilisées mais gardées pour compatibilité ─────

async def verify_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def verify_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

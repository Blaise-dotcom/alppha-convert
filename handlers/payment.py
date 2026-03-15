import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from database import add_transaction, set_premium, complete_transaction, is_premium
from config import (
    STARS_PRICE_WEEKLY,
    STARS_PRICE_MONTHLY,
    TON_PRICE_WEEKLY,
    TON_PRICE_MONTHLY,
    TON_WALLET,
)

logger = logging.getLogger(__name__)


# ─── Affichage des plans ──────────────────────────────────────────────────────

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    if query:
        await query.answer()
        send_fn = query.edit_message_text
    else:
        send_fn = update.message.reply_text

    premium = is_premium(user_id)
    badge   = "✅ Tu es déjà *Premium* !\n\n" if premium else ""

    text = (
        f"💎 *Plans Premium MediaBot Pro*\n\n"
        f"{badge}"
        "✅ Téléchargements illimités\n"
        "✅ Compressions illimitées\n"
        "✅ Fichiers jusqu'à 500MB\n"
        "✅ Priorité de traitement\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *Hebdomadaire*\n"
        f"   ⭐ {STARS_PRICE_WEEKLY} Stars  ·  💎 {TON_PRICE_WEEKLY} TON\n\n"
        f"📆 *Mensuel* _(meilleur rapport qualité/prix)_\n"
        f"   ⭐ {STARS_PRICE_MONTHLY} Stars  ·  💎 {TON_PRICE_MONTHLY} TON\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [
        [
            InlineKeyboardButton(f"⭐ {STARS_PRICE_WEEKLY} Stars — Semaine",  callback_data="buy_stars_weekly"),
            InlineKeyboardButton(f"⭐ {STARS_PRICE_MONTHLY} Stars — Mois",    callback_data="buy_stars_monthly"),
        ],
        [
            InlineKeyboardButton(f"💎 {TON_PRICE_WEEKLY} TON — Semaine",      callback_data="buy_ton_weekly"),
            InlineKeyboardButton(f"💎 {TON_PRICE_MONTHLY} TON — Mois",        callback_data="buy_ton_monthly"),
        ],
        [InlineKeyboardButton("⬅️ Retour", callback_data="menu")],
    ]

    await send_fn(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ─── Paiement Stars ───────────────────────────────────────────────────────────

async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan   = query.data.replace("buy_stars_", "")  # "weekly" ou "monthly"
    price  = STARS_PRICE_WEEKLY if plan == "weekly" else STARS_PRICE_MONTHLY
    label  = "1 semaine Premium" if plan == "weekly" else "1 mois Premium"
    days   = 7 if plan == "weekly" else 30

    context.user_data["pending_stars_plan"] = plan
    context.user_data["pending_stars_days"] = days

    # Telegram Stars : currency = "XTR", amounts en entiers (pas de centimes)
    await query.message.reply_invoice(
        title=       "MediaBot Pro — Premium",
        description= f"{label} • Accès illimité à tous les outils",
        payload=     f"premium_{plan}_{query.from_user.id}",
        currency=    "XTR",
        prices=      [LabeledPrice(label, price)],
        # photo_url= "https://..." (optionnel)
    )


# ─── Pre-checkout query (obligatoire pour Telegram Stars) ────────────────────

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


# ─── Paiement Stars confirmé ─────────────────────────────────────────────────

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload  # "premium_weekly_123"
    amount  = update.message.successful_payment.total_amount     # en Stars

    plan = "weekly" if "weekly" in payload else "monthly"
    days = 7 if plan == "weekly" else 30
    until = date.today() + timedelta(days=days)

    add_transaction(user_id, plan, "XTR", amount)
    set_premium(user_id, until)

    from handlers.menu import main_keyboard
    await update.message.reply_text(
        f"🎉 *Paiement confirmé !*\n\n"
        f"💎 Tu es maintenant *Premium* jusqu'au *{until.strftime('%d/%m/%Y')}*\n"
        f"🚀 Accès illimité activé !",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


# ─── Paiement TON ─────────────────────────────────────────────────────────────

async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan  = query.data.replace("buy_ton_", "")
    price = TON_PRICE_WEEKLY if plan == "weekly" else TON_PRICE_MONTHLY
    label = "1 semaine" if plan == "weekly" else "1 mois"

    context.user_data["pending_ton_plan"] = plan

    await query.edit_message_text(
        f"💎 *Paiement TON — {label} Premium*\n\n"
        f"1️⃣ Envoie exactement *{price} TON* à cette adresse :\n"
        f"`{TON_WALLET}`\n\n"
        f"2️⃣ Une fois le paiement effectué, envoie-moi le hash de la transaction ici dans ce format :\n"
        f"`tx:HASH_ICI`\n\n"
        f"_Exemple :_\n`tx:3a8f2b...`\n\n"
        f"⚠️ Envoie exactement *{price} TON* — montant incorrect = non traité.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Retour aux plans", callback_data="premium")]
        ]),
    )


# ─── Vérification du hash TON ─────────────────────────────────────────────────

async def verify_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """L'utilisateur envoie 'tx:HASH' pour déclarer son paiement TON."""
    text    = update.message.text.strip()
    tx_hash = text[3:].strip()  # retire le préfixe "tx:"

    if len(tx_hash) < 10:
        await update.message.reply_text(
            "❌ Hash invalide. Assure-toi d'envoyer :\n`tx:HASH_DE_LA_TRANSACTION`",
            parse_mode="Markdown",
        )
        return

    user_id = update.effective_user.id
    plan    = context.user_data.get("pending_ton_plan", "monthly")
    price   = TON_PRICE_WEEKLY if plan == "weekly" else TON_PRICE_MONTHLY
    days    = 7 if plan == "weekly" else 30
    until   = date.today() + timedelta(days=days)

    # ──────────────────────────────────────────────────────────────────────────
    # 🔧 EN PRODUCTION : vérifier le tx sur la blockchain TON via TonCenter API
    #
    # import httpx
    # r = httpx.get(f"https://toncenter.com/api/v2/getTransaction?tx_hash={tx_hash}")
    # data = r.json()
    # Vérifier : montant == price, destination == TON_WALLET, statut == OK
    # ──────────────────────────────────────────────────────────────────────────

    # Pour la version MVP on accepte tous les hashs (à remplacer par la vraie vérification)
    tx_id = add_transaction(user_id, plan, "TON", price, tx_hash)
    complete_transaction(tx_id)
    set_premium(user_id, until)

    from handlers.menu import main_keyboard
    await update.message.reply_text(
        f"✅ *Paiement TON enregistré !*\n\n"
        f"💎 Tu es maintenant *Premium* jusqu'au *{until.strftime('%d/%m/%Y')}*\n"
        f"🚀 Accès illimité activé !",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )

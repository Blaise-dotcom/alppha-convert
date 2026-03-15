from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import ensure_user, get_usage, is_premium
from config import FREE_DOWNLOADS_PER_DAY, FREE_COMPRESSIONS_PER_DAY, FREE_MAX_FILE_SIZE_MB, PREMIUM_MAX_FILE_SIZE_MB

LOGO = "⚡"

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Télécharger",  callback_data="download"),
            InlineKeyboardButton("⚙️ Compresser",   callback_data="compress"),
        ],
        [
            InlineKeyboardButton("💎 Premium",      callback_data="premium"),
            InlineKeyboardButton("📊 Mon usage",    callback_data="usage"),
        ],
        [InlineKeyboardButton("ℹ️ Aide",            callback_data="help")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)

    premium = is_premium(user.id)
    badge   = "💎 *Premium*" if premium else "🆓 Gratuit"

    await update.message.reply_text(
        f"{LOGO} *Alpha Convert*\n\n"
        f"👋 Bienvenue *{user.first_name}* !\n"
        f"🏷️ Plan actuel : {badge}\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📥 *Télécharger* — YouTube, Instagram, TikTok\n"
        "⚙️ *Compresser* — Convertis et compresse tes vidéos\n"
        "💎 *Premium* — Accès illimité\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Choisis une option :",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{LOGO} *Alpha Convert — Menu Principal*\n\n"
        "👇 Choisis une option :",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def show_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    usage   = get_usage(user_id)
    premium = is_premium(user_id)

    if premium:
        text = (
            "📊 *Ton usage aujourd'hui*\n\n"
            "💎 Plan *Premium* — accès illimité ♾️\n\n"
            f"📥 Téléchargements : {usage['downloads']}\n"
            f"⚙️ Compressions   : {usage['compressions']}"
        )
    else:
        dl_left  = max(0, FREE_DOWNLOADS_PER_DAY - usage["downloads"])
        cmp_left = max(0, FREE_COMPRESSIONS_PER_DAY - usage["compressions"])
        text = (
            "📊 *Ton usage aujourd'hui*\n\n"
            f"📥 Téléchargements : {usage['downloads']}/{FREE_DOWNLOADS_PER_DAY}  ({dl_left} restant(s))\n"
            f"⚙️ Compressions   : {usage['compressions']}/{FREE_COMPRESSIONS_PER_DAY}  ({cmp_left} restant(s))\n\n"
            f"📁 Taille max : {FREE_MAX_FILE_SIZE_MB}MB\n\n"
            "💡 Passe en *Premium* pour un accès illimité !"
        )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Passer Premium", callback_data="premium")],
            [InlineKeyboardButton("⬅️ Retour",         callback_data="menu")],
        ]),
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{LOGO} *Alpha Convert — Aide*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📥 *Télécharger*\n"
        "• Colle un lien YouTube, Instagram ou TikTok\n"
        "• Choisis MP3 ou MP4, puis la qualité\n"
        f"• Gratuit : {FREE_DOWNLOADS_PER_DAY} téléchargements/jour | max {FREE_MAX_FILE_SIZE_MB}MB\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "⚙️ *Compresser*\n"
        "• Cette fonctionnalité est temporairement en maintenance 🔧\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💎 *Premium*\n"
        f"• Illimité + fichiers jusqu'à {PREMIUM_MAX_FILE_SIZE_MB}MB\n"
        "• Paiement : ⭐ Stars · 💎 TON · 💵 USDT\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🆘 *Support* : @AlphaConvertSupport\\_bot",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Retour", callback_data="menu")]
        ]),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Annulé.", reply_markup=main_keyboard())
    return ConversationHandler.END

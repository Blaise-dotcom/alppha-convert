"""
handlers/admin.py  —  Panneau d'administration du bot Alpha Convert
"""
import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

from config import ADMIN_IDS
from database import set_premium, get_conn

logger = logging.getLogger(__name__)

ADMIN_WAITING_USER_ID   = 50
ADMIN_WAITING_PLAN      = 51
ADMIN_WAITING_REVOKE_ID = 52


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.effective_message.reply_text("⛔ Accès refusé.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Donner Premium",   callback_data="adm_give")],
        [InlineKeyboardButton("❌ Révoquer Premium", callback_data="adm_revoke")],
        [InlineKeyboardButton("📋 Liste Premium",    callback_data="adm_list")],
        [InlineKeyboardButton("📊 Stats globales",   callback_data="adm_stats")],
    ])
    await update.effective_message.reply_text(
        "🛠 Panneau Admin — Alpha Convert\n\nChoisis une action :",
        reply_markup=keyboard,
    )


# ─── Entry points séparés pour la conversation ───────────────────────────────

async def adm_give_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point pour donner le premium"""
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Accès refusé.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text(
        "➕ Donner Premium\n\nEnvoie l'ID Telegram de l'utilisateur :"
    )
    return ADMIN_WAITING_USER_ID


async def adm_revoke_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point pour révoquer le premium"""
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Accès refusé.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text(
        "❌ Révoquer Premium\n\nEnvoie l'ID Telegram de l'utilisateur à révoquer :"
    )
    return ADMIN_WAITING_REVOKE_ID


# ─── Callbacks admin (stats, liste, retour) ───────────────────────────────────

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        await query.answer("⛔ Accès refusé.", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "adm_list":
        rows = _get_premium_users()
        if not rows:
            text = "📋 Utilisateurs Premium\n\nAucun utilisateur premium."
        else:
            lines = ["📋 Utilisateurs Premium actifs :\n"]
            for r in rows:
                lines.append(
                    f"• {r['user_id']} — @{r['username'] or '?'} — {r['first_name'] or ''}\n"
                    f"  Expire : {r['premium_until']}"
                )
            text = "\n".join(lines)
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data="adm_back")]]),
        )

    elif data == "adm_stats":
        stats = _get_stats()
        text = (
            "📊 Statistiques globales\n\n"
            f"👥 Utilisateurs total : {stats['total_users']}\n"
            f"💎 Utilisateurs premium : {stats['premium_users']}\n"
            f"📥 Téléchargements aujourd'hui : {stats['downloads_today']}\n"
            f"⚙️ Compressions aujourd'hui : {stats['compressions_today']}\n"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data="adm_back")]]),
        )

    elif data == "adm_back":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Donner Premium",   callback_data="adm_give")],
            [InlineKeyboardButton("❌ Révoquer Premium", callback_data="adm_revoke")],
            [InlineKeyboardButton("📋 Liste Premium",    callback_data="adm_list")],
            [InlineKeyboardButton("📊 Stats globales",   callback_data="adm_stats")],
        ])
        await query.edit_message_text(
            "🛠 Panneau Admin — Alpha Convert\n\nChoisis une action :",
            reply_markup=keyboard,
        )

    elif data.startswith("adm_plan_"):
        plan = data.replace("adm_plan_", "")
        target_id = context.user_data.get("adm_target_id")
        if not target_id:
            await query.edit_message_text("❌ Session expirée, recommence.")
            return ConversationHandler.END

        days_map = {
            "1month": 30, "3months": 90, "6months": 180,
            "1year": 365, "lifetime": 36500,
            "weekly": 7, "monthly": 30,
        }
        days  = days_map.get(plan, 30)
        until = date.today() + timedelta(days=days)
        set_premium(target_id, until)

        label_map = {
            "1month": "1 mois", "3months": "3 mois", "6months": "6 mois",
            "1year": "1 an", "lifetime": "À vie ♾️",
            "weekly": "1 semaine", "monthly": "1 mois",
        }
        label = label_map.get(plan, plan)
        until_str = "À vie ♾️" if plan == "lifetime" else until.strftime("%d/%m/%Y")

        # Notifier l'utilisateur
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 Félicitations !\n\n"
                     f"💎 Tu viens de recevoir un accès Premium sur Alpha Convert !\n\n"
                     f"📅 Plan : {label}\n"
                     f"📆 Valide jusqu'au : {until_str}\n\n"
                     f"🚀 Tu peux maintenant télécharger sans limite et accéder à tous les formats !\n\n"
                     f"Merci de ta confiance 🙏",
            )
            notif = "\n\n📩 Utilisateur notifié."
        except Exception as e:
            logger.warning(f"Impossible de notifier l'utilisateur {target_id} : {e}")
            notif = "\n\n⚠️ Impossible de notifier l'utilisateur (il n'a peut-être jamais démarré le bot)."

        await query.edit_message_text(
            f"✅ Premium activé !\n\n"
            f"👤 User ID : {target_id}\n"
            f"📅 Plan : {label}\n"
            f"📆 Expire le : {until_str}"
            f"{notif}",
        )
        context.user_data.pop("adm_target_id", None)
        return ConversationHandler.END


# ─── Conversation : donner premium ───────────────────────────────────────────

async def adm_receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ ID invalide. Envoie un nombre entier.")
        return ADMIN_WAITING_USER_ID

    context.user_data["adm_target_id"] = target_id
    info = _get_user_info(target_id)
    user_label = f"@{info['username']}" if info and info.get("username") else f"ID {target_id}"

    await update.message.reply_text(
        f"👤 Utilisateur : {user_label}\n\nChoisis la durée du plan :",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 1 Mois",   callback_data="adm_plan_1month")],
            [InlineKeyboardButton("📦 3 Mois",   callback_data="adm_plan_3months")],
            [InlineKeyboardButton("🏆 6 Mois",   callback_data="adm_plan_6months")],
            [InlineKeyboardButton("👑 1 An",     callback_data="adm_plan_1year")],
            [InlineKeyboardButton("♾️ À vie",    callback_data="adm_plan_lifetime")],
        ]),
    )
    return ADMIN_WAITING_PLAN


# ─── Conversation : révoquer premium ─────────────────────────────────────────

async def adm_receive_revoke_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ ID invalide.")
        return ADMIN_WAITING_REVOKE_ID

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_premium = FALSE, premium_until = NULL WHERE user_id = %s",
                (target_id,)
            )
        conn.commit()

    await update.message.reply_text(f"✅ Premium révoqué pour l'utilisateur {target_id}.")
    return ConversationHandler.END


# ─── Helpers DB ───────────────────────────────────────────────────────────────

def _get_premium_users() -> list:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id, username, first_name, premium_until
                    FROM users
                    WHERE is_premium = TRUE AND premium_until >= %s
                    ORDER BY premium_until DESC
                """, (date.today(),))
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"_get_premium_users: {e}")
        return []


def _get_user_info(user_id: int) -> dict | None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, username, first_name FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                if row:
                    return {"user_id": row[0], "username": row[1], "first_name": row[2]}
    except Exception as e:
        logger.error(f"_get_user_info: {e}")
    return None


def _get_stats() -> dict:
    today = date.today()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM users WHERE is_premium = TRUE AND premium_until >= %s", (today,))
                premium = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(downloads),0) FROM daily_usage WHERE usage_date = %s", (today,))
                dl = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(compressions),0) FROM daily_usage WHERE usage_date = %s", (today,))
                cp = cur.fetchone()[0]
        return {"total_users": total, "premium_users": premium, "downloads_today": dl, "compressions_today": cp}
    except Exception as e:
        logger.error(f"_get_stats: {e}")
        return {"total_users": 0, "premium_users": 0, "downloads_today": 0, "compressions_today": 0}


# ─── Construction du ConversationHandler admin ───────────────────────────────

def build_admin_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(adm_give_entry,   pattern="^adm_give$"),
            CallbackQueryHandler(adm_revoke_entry, pattern="^adm_revoke$"),
        ],
        states={
            ADMIN_WAITING_USER_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_receive_user_id)],
            ADMIN_WAITING_PLAN:      [CallbackQueryHandler(admin_callback, pattern="^adm_plan_")],
            ADMIN_WAITING_REVOKE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_receive_revoke_id)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False,
        allow_reentry=True,
    )

import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_usage, increment_usage, is_premium, ensure_user
from services.downloader import detect_platform, download_media, get_video_info
from config import (
    FREE_DOWNLOADS_PER_DAY,
    FREE_MAX_FILE_SIZE_MB,
    PREMIUM_MAX_FILE_SIZE_MB,
)

logger = logging.getLogger(__name__)

WAITING_LINK    = 10
WAITING_FORMAT  = 11
WAITING_QUALITY = 12


def _clean(text: str) -> str:
    """Supprime les caractères spéciaux pour éviter les erreurs Telegram."""
    return "".join(c for c in text if c.isalnum() or c in " .,!?()+-")


async def start_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    ensure_user(user_id, query.from_user.username, query.from_user.first_name)

    context.user_data.clear()

    usage   = get_usage(user_id)
    premium = is_premium(user_id)

    if not premium and usage["downloads"] >= FREE_DOWNLOADS_PER_DAY:
        await query.edit_message_text(
            f"❌ Limite atteinte !\n\n"
            f"Tu as utilisé tes {FREE_DOWNLOADS_PER_DAY} téléchargements gratuits aujourd'hui.\n"
            "Le quota se renouvelle chaque jour à minuit.\n\n"
            "💎 Passe en Premium pour un accès illimité !",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Voir les plans", callback_data="premium")],
                [InlineKeyboardButton("⬅️ Retour",         callback_data="menu")],
            ]),
        )
        return ConversationHandler.END

    remaining = "illimité ♾️" if premium else f"{FREE_DOWNLOADS_PER_DAY - usage['downloads']} restant(s)"
    max_size  = PREMIUM_MAX_FILE_SIZE_MB if premium else FREE_MAX_FILE_SIZE_MB

    await query.edit_message_text(
        "📥 Téléchargement de média\n\n"
        "Envoie-moi le lien de la vidéo :\n\n"
        "🔴 YouTube\n"
        "📸 Instagram (posts, reels)\n"
        "🎵 TikTok\n\n"
        f"📊 Quota aujourd'hui : {remaining}\n"
        f"📁 Taille max : {max_size}MB\n\n"
        "Envoie /cancel pour annuler",
    )
    return WAITING_LINK


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url      = update.message.text.strip()
    platform = detect_platform(url)

    if not platform:
        await update.message.reply_text(
            "❌ Lien non reconnu.\n\n"
            "J'accepte les liens :\n"
            "• youtube.com / youtu.be\n"
            "• instagram.com\n"
            "• tiktok.com\n\n"
            "Essaie encore ou /cancel"
        )
        return WAITING_LINK

    context.user_data["url"]      = url
    context.user_data["platform"] = platform

    emoji_map = {"youtube": "🔴", "instagram": "📸", "tiktok": "🎵"}
    msg = await update.message.reply_text(f"{emoji_map[platform]} Analyse du lien en cours...")

    if platform == "instagram":
        await msg.edit_text(
            "📸 Instagram\n\n"
            "Nous travaillons sur cette option.\n\n"
            "✅ YouTube et TikTok fonctionnent normalement.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Retour au menu", callback_data="menu")],
            ]),
        )
        return ConversationHandler.END

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, get_video_info, url)
        context.user_data["video_info"] = info

        dur     = info["duration"]
        dur_str = f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "?"
        title   = _clean(info["title"][:50])

        await msg.edit_text(
            f"✅ Vidéo trouvée !\n\n"
            f"📌 {title}\n"
            f"⏱ Durée : {dur_str}\n"
            f"👤 {_clean(info['uploader'])}\n\n"
            "Choisis le format :",
            reply_markup=_format_keyboard(),
        )
    except Exception as e:
        logger.warning(f"Impossible de lire les infos : {e}")
        await msg.edit_text(
            "⚠️ Infos non disponibles, je vais quand même essayer.\n\n"
            "Choisis le format :",
            reply_markup=_format_keyboard(),
        )

    return WAITING_FORMAT


async def handle_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    fmt = query.data.replace("fmt_", "")
    context.user_data["format"] = fmt

    if fmt == "mp3":
        context.user_data["quality"] = "720"
        await query.edit_message_text("⏳ Téléchargement MP3 en cours...\nCa peut prendre quelques secondes.")
        await _do_download(query.message, context, query.from_user.id)
        return ConversationHandler.END

    await query.edit_message_text(
        "🎬 Choisis la qualité vidéo :",
        reply_markup=_quality_keyboard(),
    )
    return WAITING_QUALITY


async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality = query.data.replace("qual_", "")
    context.user_data["quality"] = quality

    labels = {"1080": "1080p HD", "720": "720p", "480": "480p", "360": "360p"}
    await query.edit_message_text(
        f"⏳ Téléchargement en {labels.get(quality, quality)} en cours...\n"
        "Ca peut prendre quelques secondes.",
    )
    await _do_download(query.message, context, query.from_user.id)
    return ConversationHandler.END


async def _do_download(message, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    url     = context.user_data.get("url", "")
    fmt     = context.user_data.get("format", "mp4")
    quality = context.user_data.get("quality", "720")
    premium = is_premium(user_id)
    max_mb  = PREMIUM_MAX_FILE_SIZE_MB if premium else FREE_MAX_FILE_SIZE_MB

    try:
        await message.get_bot().send_chat_action(
            chat_id=message.chat_id,
            action="upload_video" if fmt != "mp3" else "upload_voice"
        )
    except Exception:
        pass

    try:
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_media, url, fmt, quality)

        if not file_path or not os.path.exists(file_path):
            await message.reply_text(
                "❌ Téléchargement échoué.\n"
                "La vidéo est peut-être privée ou le lien a expiré."
            )
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if size_mb > max_mb:
            os.remove(file_path)
            tip = "\n\n💎 Passe en Premium pour des fichiers jusqu'à 500MB !" if not premium else ""
            await message.reply_text(
                f"❌ Fichier trop lourd !\n\n"
                f"Taille : {size_mb:.1f}MB\nLimite : {max_mb}MB{tip}"
            )
            return

        try:
            await message.get_bot().send_chat_action(
                chat_id=message.chat_id,
                action="upload_video" if fmt != "mp3" else "upload_voice"
            )
        except Exception:
            pass

        safe_title = _clean(title[:100])

        with open(file_path, "rb") as f:
            if fmt == "mp3":
                await message.reply_audio(
                    f,
                    title=safe_title[:64],
                    filename=f"{safe_title[:50]}.mp3",
                    caption="Via Alpha Convert",
                )
            else:
                await message.reply_video(
                    f,
                    caption=f"Via Alpha Convert",
                    supports_streaming=True,
                )

        increment_usage(user_id, "downloads")
        os.remove(file_path)

        from handlers.menu import main_keyboard
        await message.reply_text(
            "✅ Téléchargement terminé !",
            reply_markup=main_keyboard()
        )

    except Exception as e:
        logger.error(f"Erreur download : {e}")
        try:
            if 'file_path' in locals() and file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        from handlers.menu import main_keyboard
        await message.reply_text(
            "❌ Erreur lors du téléchargement.\n"
            "Vérifie que la vidéo est publique et réessaie.",
            reply_markup=main_keyboard()
        )


def _format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 MP4 (vidéo)", callback_data="fmt_mp4"),
            InlineKeyboardButton("🎵 MP3 (audio)", callback_data="fmt_mp3"),
        ]
    ])


def _quality_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 1080p HD",           callback_data="qual_1080")],
        [InlineKeyboardButton("📺 720p",               callback_data="qual_720")],
        [InlineKeyboardButton("📱 480p",               callback_data="qual_480")],
        [InlineKeyboardButton("💨 360p (plus rapide)", callback_data="qual_360")],
    ])

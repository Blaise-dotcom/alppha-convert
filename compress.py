import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_usage, increment_usage, is_premium, ensure_user
from services.compressor import compress_video
from config import (
    FREE_COMPRESSIONS_PER_DAY,
    FREE_MAX_FILE_SIZE_MB,
    PREMIUM_MAX_FILE_SIZE_MB,
    DOWNLOAD_PATH,
    QUALITY_PRESETS,
)

logger = logging.getLogger(__name__)

# ─── États ────────────────────────────────────────────────────────────────────
WAITING_FILE          = 20
WAITING_OUTPUT_FORMAT = 21
WAITING_QUALITY_PRESET = 22

# ─── Options ──────────────────────────────────────────────────────────────────
VIDEO_FORMAT_BUTTONS = [
    ("MP4",  "ofmt_mp4"),
    ("MKV",  "ofmt_mkv"),
    ("AVI",  "ofmt_avi"),
    ("MOV",  "ofmt_mov"),
    ("WebM", "ofmt_webm"),
]
AUDIO_FORMAT_BUTTONS = [
    ("MP3",  "ofmt_mp3"),
    ("AAC",  "ofmt_aac"),
]


# ─── Entrée ───────────────────────────────────────────────────────────────────

async def start_compress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    ensure_user(user_id, query.from_user.username, query.from_user.first_name)

    usage   = get_usage(user_id)
    premium = is_premium(user_id)

    if not premium and usage["compressions"] >= FREE_COMPRESSIONS_PER_DAY:
        await query.edit_message_text(
            f"❌ *Limite atteinte !*\n\n"
            f"Tu as utilisé tes {FREE_COMPRESSIONS_PER_DAY} compressions gratuites aujourd'hui.\n\n"
            "💎 Passe en *Premium* pour un accès illimité !",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Voir les plans", callback_data="premium")],
                [InlineKeyboardButton("⬅️ Retour",         callback_data="menu")],
            ]),
        )
        return ConversationHandler.END

    remaining = "illimité ♾️" if premium else f"{FREE_COMPRESSIONS_PER_DAY - usage['compressions']} restant(s)"
    max_size  = PREMIUM_MAX_FILE_SIZE_MB if premium else FREE_MAX_FILE_SIZE_MB

    await query.edit_message_text(
        "⚙️ *Compression & Conversion*\n\n"
        f"📁 Taille max acceptée : *{max_size}MB*\n"
        f"📊 Quota aujourd'hui : *{remaining}*\n\n"
        "🎬 Formats de sortie : MP4, MKV, AVI, MOV, WebM\n"
        "🎵 Audio uniquement  : MP3, AAC\n\n"
        "👇 *Envoie-moi la vidéo à traiter :*\n"
        "_(Envoie /cancel pour annuler)_",
        parse_mode="Markdown",
    )
    return WAITING_FILE


# ─── Réception du fichier ─────────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    premium = is_premium(user_id)
    max_mb  = PREMIUM_MAX_FILE_SIZE_MB if premium else FREE_MAX_FILE_SIZE_MB

    # Accepter video ou document vidéo
    file_obj = update.message.video or update.message.document
    if not file_obj:
        await update.message.reply_text(
            "❌ Envoie une vidéo valide.\n"
            "Tu peux l'envoyer en tant que vidéo ou en tant que fichier."
        )
        return WAITING_FILE

    size_mb = file_obj.file_size / (1024 * 1024)
    if size_mb > max_mb:
        tip = "\n\n💎 Passe en *Premium* pour jusqu'à 500MB !" if not premium else ""
        await update.message.reply_text(
            f"❌ *Fichier trop lourd !*\n\n"
            f"Taille reçue : {size_mb:.1f}MB\n"
            f"Limite actuelle : {max_mb}MB{tip}",
            parse_mode="Markdown",
        )
        return WAITING_FILE

    context.user_data["compress_file_id"]   = file_obj.file_id
    context.user_data["compress_file_size"] = size_mb

    # Clavier de sélection du format
    vbtns = [InlineKeyboardButton(lbl, callback_data=cb) for lbl, cb in VIDEO_FORMAT_BUTTONS]
    abtns = [InlineKeyboardButton(lbl, callback_data=cb) for lbl, cb in AUDIO_FORMAT_BUTTONS]

    await update.message.reply_text(
        f"✅ Vidéo reçue — *{size_mb:.1f}MB*\n\n"
        "🎯 *Choisis le format de sortie :*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            vbtns[:3],    # MP4, MKV, AVI
            vbtns[3:],    # MOV, WebM
            abtns,        # MP3, AAC
        ]),
    )
    return WAITING_OUTPUT_FORMAT


# ─── Choix du format de sortie ────────────────────────────────────────────────

async def handle_output_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    fmt = query.data.replace("ofmt_", "")
    context.user_data["output_format"] = fmt

    # Clavier des niveaux de qualité
    quality_rows = [
        [InlineKeyboardButton(info["label"], callback_data=f"qpre_{key}")]
        for key, info in QUALITY_PRESETS.items()
    ]

    await query.edit_message_text(
        f"✅ Format choisi : *{fmt.upper()}*\n\n"
        "🎚️ *Choisis le niveau de qualité :*\n\n"
        "🔵 Ultra → qualité maximale, fichier lourd\n"
        "🔴 Max   → fichier très léger, qualité réduite",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(quality_rows),
    )
    return WAITING_QUALITY_PRESET


# ─── Choix de la qualité et compression ──────────────────────────────────────

async def handle_quality_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    preset  = query.data.replace("qpre_", "")
    fmt     = context.user_data["output_format"]
    file_id = context.user_data["compress_file_id"]
    in_size = context.user_data["compress_file_size"]
    user_id = query.from_user.id

    await query.edit_message_text(
        f"⚙️ Compression *{fmt.upper()}* en cours...\n"
        "_Ça peut prendre quelques secondes selon la taille._",
        parse_mode="Markdown",
    )

    try:
        os.makedirs(DOWNLOAD_PATH, exist_ok=True)
        input_path = os.path.join(DOWNLOAD_PATH, f"input_{user_id}_{file_id[:8]}.tmp")

        # Télécharge le fichier depuis Telegram
        tg_file = await query.get_bot().get_file(file_id)
        await tg_file.download_to_drive(input_path)

        # Lance la compression en thread séparé (évite de bloquer la boucle asyncio)
        loop = asyncio.get_event_loop()
        output_path = await loop.run_in_executor(
            None, compress_video, input_path, fmt, preset
        )

        out_size = os.path.getsize(output_path) / (1024 * 1024)
        ratio    = (1 - out_size / in_size) * 100 if in_size > 0 else 0
        gain_str = f"-{ratio:.1f}%" if ratio > 0 else f"+{abs(ratio):.1f}% (qualité améliorée)"

        caption = (
            f"✅ *Terminé !*\n\n"
            f"📥 Avant  : {in_size:.1f}MB\n"
            f"📤 Après  : {out_size:.1f}MB\n"
            f"💾 Gain   : {gain_str}\n"
            f"🎯 Format : {fmt.upper()}"
        )

        with open(output_path, "rb") as f:
            if fmt in ["mp3", "aac"]:
                await query.message.reply_audio(
                    f,
                    caption=caption,
                    parse_mode="Markdown",
                    filename=f"output.{fmt}",
                )
            else:
                await query.message.reply_document(
                    f,
                    caption=caption,
                    parse_mode="Markdown",
                    filename=f"output.{fmt}",
                )

        increment_usage(user_id, "compressions")
        os.remove(input_path)
        os.remove(output_path)

        from handlers.menu import main_keyboard
        await query.message.reply_text("✅ *Compression terminée !*", parse_mode="Markdown", reply_markup=main_keyboard())

    except Exception as e:
        logger.error(f"Erreur compression : {e}")
        await query.message.reply_text(
            "❌ Erreur lors de la compression.\n"
            "Le fichier est peut-être corrompu ou dans un format non supporté."
        )

    return ConversationHandler.END

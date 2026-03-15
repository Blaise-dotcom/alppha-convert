import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import ensure_user
from handlers.menu import main_keyboard

logger = logging.getLogger(__name__)

WAITING_FILE          = 20
WAITING_OUTPUT_FORMAT = 21
WAITING_QUALITY_PRESET = 22


async def start_compress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "⚙️ *Compression & Conversion*\n\n"
        "🔧 Cette fonctionnalité est actuellement en *maintenance*.\n\n"
        "Elle sera disponible très prochainement !\n"
        "Merci de ta patience 🙏",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Retour", callback_data="menu")]
        ]),
    )
    return ConversationHandler.END


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

async def handle_output_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

async def handle_quality_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

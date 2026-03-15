import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ConversationHandler,
    filters,
)

from config import BOT_TOKEN
from database import init_db

import handlers.menu    as menu
import handlers.download as dl
import handlers.compress as cp
import handlers.payment  as pay
import handlers.admin    as adm

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Conversation : Téléchargement ────────────────────────────────────────
    download_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(dl.start_download, pattern="^download$")],
        states={
            dl.WAITING_LINK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, dl.handle_link)],
            dl.WAITING_FORMAT:  [CallbackQueryHandler(dl.handle_format,  pattern=r"^fmt_")],
            dl.WAITING_QUALITY: [CallbackQueryHandler(dl.handle_quality, pattern=r"^qual_")],
        },
        fallbacks=[CommandHandler("cancel", menu.cancel)],
        per_message=False,
    )

    # ── Conversation : Compression ───────────────────────────────────────────
    compress_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cp.start_compress, pattern="^compress$")],
        states={
            cp.WAITING_FILE: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, cp.handle_file)
            ],
            cp.WAITING_OUTPUT_FORMAT: [
                CallbackQueryHandler(cp.handle_output_format, pattern=r"^ofmt_")
            ],
            cp.WAITING_QUALITY_PRESET: [
                CallbackQueryHandler(cp.handle_quality_preset, pattern=r"^qpre_")
            ],
        },
        fallbacks=[CommandHandler("cancel", menu.cancel)],
        per_message=False,
    )

    # ── Conversation : Admin (donner/révoquer premium) ───────────────────────
    admin_conv = adm.build_admin_conv()

    # ── Commandes ─────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   menu.start))
    app.add_handler(CommandHandler("menu",    menu.show_menu))
    app.add_handler(CommandHandler("premium", pay.show_plans))
    app.add_handler(CommandHandler("cancel",  menu.cancel))
    app.add_handler(CommandHandler("admin",   adm.admin_panel))

    # ── Conversations ─────────────────────────────────────────────────────────
    app.add_handler(download_conv)
    app.add_handler(compress_conv)
    app.add_handler(admin_conv)

    # ── Callbacks menu ────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(menu.show_menu,  pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(menu.show_usage, pattern="^usage$"))
    app.add_handler(CallbackQueryHandler(menu.show_help,  pattern="^help$"))

    # ── Callbacks paiement ────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(pay.show_plans, pattern="^premium$"))
    app.add_handler(CallbackQueryHandler(pay.buy_stars,  pattern=r"^buy_stars_"))
    app.add_handler(CallbackQueryHandler(pay.buy_ton,    pattern=r"^buy_ton_"))

    # ── Callbacks admin ───────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(adm.admin_callback, pattern="^adm_"))

    # ── Stars : pre-checkout + confirmation ───────────────────────────────────
    app.add_handler(PreCheckoutQueryHandler(pay.pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, pay.successful_payment))

    # ── TON : vérification du hash ────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.Regex(r"^tx:"), pay.verify_ton))

    return app


def main():
    logger.info("🚀 Démarrage de Alpha Convert...")
    init_db()
    app = build_app()
    logger.info("✅ Bot lancé — en attente de messages")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

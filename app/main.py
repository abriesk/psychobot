import logging
import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
from app.db import init_db
from app.handlers import common, consultation, admin, user_negotiation

# home_filter defined at module level for reuse
home_filter = filters.Regex("^(🏠 Домой|🏠 Գլխավոր)$")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def post_init(application):
    await init_db()
    print("Database initialized.")

def main():
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).post_init(post_init).build()

    # --- Conversation: Start & Language ---
    lang_conv = ConversationHandler(
        entry_points=[CommandHandler("start", common.start)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, common.set_language)]},
        fallbacks=[]
    )
    
    # --- Conversation: Consultation Booking ---
    booking_trigger = filters.Regex("^(Консультация|Խորհրդատվություն)$")
    
    consult_conv = ConversationHandler(
        entry_points=[MessageHandler(booking_trigger, consultation.start_consultation)],
        allow_reentry=True,
        states={
            consultation.TYPE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~home_filter, consultation.type_selected)
            ],
            consultation.TIMEZONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~home_filter, consultation.timezone_step)
            ],
            consultation.TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~home_filter, consultation.time_step)
            ],
            consultation.PROBLEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~home_filter, consultation.problem_step)
            ],
            consultation.CONTACTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~home_filter, consultation.contacts_step)
            ],
            consultation.WAITLIST_CONTACTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~home_filter, consultation.waitlist_finalize)
            ],
        },
        fallbacks=[
            MessageHandler(home_filter, common.back_to_home),
            CommandHandler("cancel", common.back_to_home)
        ]
    )
    
    # --- Admin: Proposal Conversation ---
    admin_prop_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.admin_propose_start, pattern="^adm_prop_")],
        states={"ADMIN_PROPOSE": [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.admin_propose_text)]},
        fallbacks=[
            MessageHandler(home_filter, common.back_to_home),
            CommandHandler("cancel", common.start)
        ]
    )

    # 🔧 NEW: Landing Upload Conversation
    landing_upload_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Upload Landing$"), admin.upload_landing_start)],
        states={
            admin.UPLOAD_TOPIC: [
                CallbackQueryHandler(admin.upload_topic_selected, pattern="^upload_")
            ],
            admin.UPLOAD_LANG: [
                CallbackQueryHandler(admin.upload_lang_selected, pattern="^upload_")
            ],
            admin.UPLOAD_FILE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.upload_text_received)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin.upload_landing_start, pattern="^upload_cancel$"),
            CommandHandler("cancel", common.start)
        ]
    )

    # 🔧 NEW: Price Edit Conversation
    price_edit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Edit Prices$"), admin.edit_prices_start)],
        states={
            admin.EDIT_PRICE_TYPE: [
                CallbackQueryHandler(admin.edit_price_type_selected, pattern="^price_")
            ],
            admin.EDIT_PRICE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.edit_price_value_received)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin.edit_prices_start, pattern="^price_cancel$"),
            CommandHandler("cancel", common.start)
        ]
    )

    # --- User: Counter-Proposal Conversation ---
    user_counter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_negotiation.user_negotiation_counter_start, pattern="^usr_counter_")],
        states={
            user_negotiation.USER_COUNTER_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_negotiation.user_negotiation_counter_text)
            ]
        },
        fallbacks=[
            MessageHandler(home_filter, common.back_to_home),
            CommandHandler("cancel", common.start)
        ]
    )

    # --- Handlers Registration ---
    # Conversation handlers first (order matters!)
    app.add_handler(lang_conv)
    app.add_handler(consult_conv)
    app.add_handler(admin_prop_conv)
    app.add_handler(landing_upload_conv)  # 🔧 NEW
    app.add_handler(price_edit_conv)      # 🔧 NEW
    app.add_handler(user_counter_conv)
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin.admin_start))
    app.add_handler(MessageHandler(filters.Regex("^Toggle Availability$"), admin.toggle_availability))
    app.add_handler(MessageHandler(filters.Regex("^Pending Requests$"), admin.list_pending))
    
    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^adm_(view|approve|reject)_"))
    
    # User negotiation callbacks
    app.add_handler(CallbackQueryHandler(user_negotiation.user_negotiation_yes, pattern="^usr_yes_"))
    
    # Main Menu Navigation
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~home_filter & ~booking_trigger, 
        common.handle_menu_click
    ))

    # Home button handler
    app.add_handler(MessageHandler(home_filter, common.back_to_home))

    app.run_polling()

if __name__ == '__main__':
    main()
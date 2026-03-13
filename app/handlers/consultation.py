from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from app.db import AsyncSessionLocal
from app.models import User, Request, RequestType, RequestStatus
from app.utils import get_settings
from app.translations import get_text
from sqlalchemy import select
import os

# States
TYPE_SELECT, TIMEZONE, TIME, PROBLEM, CONTACTS, WAITLIST_CONTACTS = range(6)

# 🔧 HELPER: Create home keyboard with lang
def get_home_keyboard(lang):
    """Returns a keyboard with just the Home button"""
    return ReplyKeyboardMarkup(
        [[get_text(lang, "menu_home")]], 
        resize_keyboard=True
    )

# 🔧 NEW HELPER: Get main menu keyboard
def get_main_menu_keyboard(lang):
    """Returns the full main menu keyboard"""
    menu = [
        [get_text(lang, "menu_consultation")],
        [get_text(lang, "menu_terms"), get_text(lang, "menu_qual")],
        [get_text(lang, "menu_about")],
        [get_text(lang, "menu_home")]
    ]
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)

async def start_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        lang = user.language if user else os.getenv('DEFAULT_LANGUAGE', 'ru')
        settings = await get_settings(session)
    
    context.user_data['lang'] = lang
    
    if not settings.availability_on:
        # Waitlist flow
        await update.message.reply_text(get_text(lang, "waitlist_intro"))
        
        # 🔧 CHANGED: Add home button to waitlist flow
        await update.message.reply_text(
            get_text(lang, "ask_problem"),
            reply_markup=get_home_keyboard(lang)
        )
        
        # Send references landing if exists
        path = f"/app/landings/references_{lang}.html"
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                await update.message.reply_html(f.read())
                
        return WAITLIST_CONTACTS
    else:
        # Active flow
        kb = [[get_text(lang, "btn_online"), get_text(lang, "btn_onsite")],[get_text(lang, "menu_home")]]
        await update.message.reply_text(
            get_text(lang, "menu_consultation"),
            reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        )
        return TYPE_SELECT

async def type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    text = update.message.text
    
    async with AsyncSessionLocal() as session:
        settings = await get_settings(session)
    
    if text == get_text(lang, "btn_onsite"):
        link = os.getenv("CLINIC_ONSITE_LINK")
        await update.message.reply_text(f"Link: {link}", reply_markup=get_main_menu_keyboard(lang))
        return ConversationHandler.END
    
    # Online selected
    context.user_data['is_online'] = True
    
    # Ask Type: Individual vs Couple
    btn_ind = get_text(lang, "btn_individual", price=settings.individual_price)
    btn_cpl = get_text(lang, "btn_couple", price=settings.couple_price)
    
    kb = [[btn_ind], [btn_cpl], [get_text(lang, "menu_home")]]
    await update.message.reply_text(
        "Type?", 
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return TIMEZONE

async def timezone_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    text = update.message.text
    
    if "Individual" in text or "Индивидуальная" in text or "Անհատական" in text:
        context.user_data['req_type'] = RequestType.INDIVIDUAL
    else:
        context.user_data['req_type'] = RequestType.COUPLE
    
    # 🔧 CHANGED: Add home button instead of removing keyboard
    await update.message.reply_text(
        get_text(lang, "ask_timezone"), 
        reply_markup=get_home_keyboard(lang)
    )
    return TIME

async def time_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['timezone'] = update.message.text
    lang = context.user_data.get('lang', 'ru')
    
    # 🔧 CHANGED: Keep home button visible
    await update.message.reply_text(
        get_text(lang, "ask_time"),
        reply_markup=get_home_keyboard(lang)
    )
    return PROBLEM

async def problem_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desired_time'] = update.message.text
    lang = context.user_data.get('lang', 'ru')
    
    # 🔧 CHANGED: Keep home button visible
    await update.message.reply_text(
        get_text(lang, "ask_problem"),
        reply_markup=get_home_keyboard(lang)
    )
    return CONTACTS

async def contacts_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['problem'] = update.message.text
    lang = context.user_data.get('lang', 'ru')

    req_type = context.user_data.get('req_type')
    if not req_type:
        await update.message.reply_text(get_text(lang, "error_generic"))
        return ConversationHandler.END

    # Finalize Request
    async with AsyncSessionLocal() as session:
        req = Request(
            user_id=update.effective_user.id,
            type=req_type,
            timezone=context.user_data.get('timezone'),
            desired_time=context.user_data.get('desired_time'),
            problem=context.user_data.get('problem'),
            status=RequestStatus.PENDING
        )
        session.add(req)
        await session.commit()
        await session.refresh(req)
        
        # Notify Admin
        admin_text = (
            f"🔔 <b>New Request</b>\nUUID: <code>{req.request_uuid}</code>\n"
            f"Type: {req.type.value}\nTime: {req.desired_time}\nProb: {req.problem}"
        )
        
        btns = [
            [InlineKeyboardButton("Approve", callback_data=f"adm_approve_{req.id}")],
            [InlineKeyboardButton("Propose Alt", callback_data=f"adm_prop_{req.id}")],
            [InlineKeyboardButton("Reject", callback_data=f"adm_reject_{req.id}")]
        ]
        
        # 🔧 FIXED: Convert admin_id to int and handle errors
        admin_ids = os.getenv("ADMIN_IDS", "")
        if admin_ids:
            for admin_id in admin_ids.split(","):
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_id.strip()), 
                        text=admin_text, 
                        reply_markup=InlineKeyboardMarkup(btns), 
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Failed to notify admin {admin_id}: {e}")

    await update.message.reply_text(
        get_text(lang, "confirm_sent"),
        reply_markup=get_main_menu_keyboard(lang)
    )
    return ConversationHandler.END

async def waitlist_finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'ru')
    text = update.message.text
    
    async with AsyncSessionLocal() as session:
        req = Request(
            user_id=update.effective_user.id,
            type=RequestType.WAITLIST,
            problem=text,
            status=RequestStatus.PENDING
        )
        session.add(req)
        await session.commit()
        
        # Notify Admin
        admin_text = f"⏳ <b>Waitlist Add</b>\nUser: {update.effective_user.id}\nData: {text}"
        
        # 🔧 FIXED: Convert admin_id to int and handle errors
        admin_ids = os.getenv("ADMIN_IDS", "")
        if admin_ids:
            for admin_id in admin_ids.split(","):
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_id.strip()), 
                        text=admin_text, 
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Failed to notify admin {admin_id}: {e}")

    await update.message.reply_text(
        get_text(lang, "confirm_sent"),
        reply_markup=get_main_menu_keyboard(lang)
        #reply_markup=ReplyKeyboardRemove()  # Remove for final message
    )
    return ConversationHandler.END

# Waitlist entry captures problem then contacts
async def waitlist_capture_problem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_problem'] = update.message.text
    lang = context.user_data.get('lang', 'ru')
    
    # 🔧 CHANGED: Keep home button visible
    await update.message.reply_text(
        get_text(lang, "waitlist_contacts"),
        reply_markup=get_home_keyboard(lang)
    )
    return WAITLIST_CONTACTS
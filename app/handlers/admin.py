from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from app.db import AsyncSessionLocal
from app.models import Request, RequestStatus, Negotiation, SenderType, Settings, User
from app.translations import get_text
from sqlalchemy import select
import os

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# 🔧 NEW: Conversation states for admin features
UPLOAD_TOPIC, UPLOAD_LANG, UPLOAD_FILE = range(3)
EDIT_PRICE_TYPE, EDIT_PRICE_VALUE = range(2)

# 🔧 CONSTANTS: Available topics and languages
LANDING_TOPICS = {
    "work_terms": "Work Terms",
    "qualification": "Qualification",
    "about_psychotherapy": "About Psychotherapy",
    "references": "References"
}

LANGUAGES = {
    "ru": "Russian (Русский)",
    "am": "Armenian (Հայերեն)"
}

def is_admin(user_id):
    return user_id in ADMIN_IDS

# 🔧 HELPER: Get user language from database
async def get_user_language(user_id):
    """Fetch user's language preference from database"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user.language if user else os.getenv('DEFAULT_LANGUAGE', 'ru')

# 🔧 HELPER: Notify admins with error handling
async def notify_admins(context, text, reply_markup=None, parse_mode="HTML"):
    """Send notification to all admins with proper error handling"""
    if not ADMIN_IDS:
        print("Warning: No admin IDs configured")
        return
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    kb = [
        ["Toggle Availability", "Upload Landing"],
        ["Pending Requests", "Edit Prices"]
    ]
    await update.message.reply_text("Admin Panel", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def toggle_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Settings).where(Settings.id == 1))
        st = result.scalar_one()
        st.availability_on = not st.availability_on
        await session.commit()
        state = "ON" if st.availability_on else "OFF"
    
    await update.message.reply_text(f"Availability is now: {state}")

async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    async with AsyncSessionLocal() as session:
        # Order by created_at descending (newest first)
        result = await session.execute(
            select(Request)
            .where(Request.status.in_([RequestStatus.PENDING, RequestStatus.NEGOTIATING]))
            .order_by(Request.created_at.desc())
        )
        reqs = result.scalars().all()
        
        if not reqs:
            await update.message.reply_text("No pending requests.")
            return
        
        # Send summary first
        await update.message.reply_text(
            f"?? <b>Pending Requests: {len(reqs)}</b>\n"
            f"Showing all requests requiring action...",
            parse_mode="HTML"
        )
        
        # Then send each request individually with slight delay
        import asyncio
        for i, r in enumerate(reqs, 1):
            txt = (
                f"<b>Request #{i} of {len(reqs)}</b>\n"
                f"????????????????????\n"
                f"<b>ID:</b> {r.id} | <b>UUID:</b> <code>{r.request_uuid}</code>\n"
                f"<b>Type:</b> {r.type.value}\n"
                f"<b>Status:</b> {r.status.value}\n"
                f"<b>Time:</b> {r.desired_time or 'N/A'}\n"
                f"<b>User:</b> {r.user_id}"
            )
            btns = [[InlineKeyboardButton("?? Open Details", callback_data=f"adm_view_{r.id}")]]
            await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")
            
            # Small delay to avoid rate limiting (only if more than 3 requests)
            if len(reqs) > 3 and i < len(reqs):
                await asyncio.sleep(0.3)

# ============================================================================
# 🔧 NEW: LANDING UPLOAD SYSTEM
# ============================================================================

async def upload_landing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start landing upload conversation - select topic"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END
    
    # Create inline keyboard with topics
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"upload_topic_{key}")]
        for key, name in LANDING_TOPICS.items()
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])
    
    await update.message.reply_text(
        "📄 <b>Upload Landing Page</b>\n\nSelect topic:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return UPLOAD_TOPIC

async def upload_topic_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topic selection, ask for language"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "upload_cancel":
        await query.edit_message_text("Upload cancelled.")
        return ConversationHandler.END
    
    # Extract topic from callback data
    topic = query.data.replace("upload_topic_", "")
    if topic not in LANDING_TOPICS:
        await query.edit_message_text("Invalid topic.")
        return ConversationHandler.END
    
    # Store topic in context
    context.user_data['upload_topic'] = topic
    
    # Create language selection keyboard
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"upload_lang_{key}")]
        for key, name in LANGUAGES.items()
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])
    
    await query.edit_message_text(
        f"📄 <b>Upload Landing: {LANDING_TOPICS[topic]}</b>\n\nSelect language:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return UPLOAD_LANG

async def upload_lang_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection, ask for file"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "upload_cancel":
        await query.edit_message_text("Upload cancelled.")
        return ConversationHandler.END
    
    # Extract language from callback data
    lang = query.data.replace("upload_lang_", "")
    if lang not in LANGUAGES:
        await query.edit_message_text("Invalid language.")
        return ConversationHandler.END
    
    # Store language in context
    context.user_data['upload_lang'] = lang
    
    topic = context.user_data.get('upload_topic')
    await query.edit_message_text(
        f"📄 <b>Upload Landing</b>\n"
        f"Topic: {LANDING_TOPICS[topic]}\n"
        f"Language: {LANGUAGES[lang]}\n\n"
        f"Now type or paste the content.\n\n"
        f"<b>Supported formatting:</b>\n"
        f"<code>&lt;b&gt;bold&lt;/b&gt;</code>, <code>&lt;i&gt;italic&lt;/i&gt;</code>, <code>&lt;u&gt;underline&lt;/u&gt;</code>\n"
        f"<code>&lt;a href=\"url\"&gt;link&lt;/a&gt;</code>\n"
        f"<code>&lt;code&gt;code&lt;/code&gt;</code>, <code>&lt;pre&gt;preformatted&lt;/pre&gt;</code>",
        parse_mode="HTML"
    )
    return UPLOAD_FILE

async def upload_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text content and save as landing file"""
    if not update.message.text:
        await update.message.reply_text("? Please send text content.")
        return UPLOAD_FILE
    
    content_text = update.message.text
    topic = context.user_data.get('upload_topic')
    lang = context.user_data.get('upload_lang')
    
    # Validate content length (Telegram message limit is 4096 chars)
    if len(content_text) > 4000:
        await update.message.reply_text(
            "?? Content is too long. Please shorten it to under 4000 characters."
        )
        return UPLOAD_FILE
    
    try:
        # Ensure landings directory exists
        os.makedirs("/app/landings", exist_ok=True)
        
        # Save with standard naming: {topic}_{lang}.html
        file_path = f"/app/landings/{topic}_{lang}.html"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content_text)
        
        await update.message.reply_text(
            f"? <b>Landing saved successfully!</b>\n\n"
            f"Topic: {LANDING_TOPICS[topic]}\n"
            f"Language: {LANGUAGES[lang]}\n"
            f"Length: {len(content_text)} characters",
            parse_mode="HTML"
        )
        
        # Clear context
        context.user_data.pop('upload_topic', None)
        context.user_data.pop('upload_lang', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"? Error saving content: {e}")
        print(f"Landing upload error: {e}")
        return ConversationHandler.END

        
    except Exception as e:
        await update.message.reply_text(f"❌ Error saving file: {e}")
        print(f"Landing upload error: {e}")
        return ConversationHandler.END

# ============================================================================
# 🔧 NEW: PRICE EDITING SYSTEM
# ============================================================================

async def edit_prices_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start price editing conversation - select type"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END
    
    # Get current prices
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Settings).where(Settings.id == 1))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
            await session.commit()
    
    # Create type selection keyboard
    buttons = [
        [InlineKeyboardButton(f"Individual (current: {settings.individual_price})", 
                            callback_data="price_type_individual")],
        [InlineKeyboardButton(f"Couple (current: {settings.couple_price})", 
                            callback_data="price_type_couple")],
        [InlineKeyboardButton("❌ Cancel", callback_data="price_cancel")]
    ]
    
    await update.message.reply_text(
        "💰 <b>Edit Prices</b>\n\nSelect consultation type:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return EDIT_PRICE_TYPE

async def edit_price_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle type selection, ask for new price"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "price_cancel":
        await query.edit_message_text("Price editing cancelled.")
        return ConversationHandler.END
    
    # Extract type from callback data
    price_type = query.data.replace("price_type_", "")
    if price_type not in ["individual", "couple"]:
        await query.edit_message_text("Invalid type.")
        return ConversationHandler.END
    
    # Store type in context
    context.user_data['price_type'] = price_type
    
    await query.edit_message_text(
        f"💰 <b>Edit {price_type.capitalize()} Price</b>\n\n"
        f"Enter new price (e.g., '50 USD / 60 min' or '€60/hour'):",
        parse_mode="HTML"
    )
    return EDIT_PRICE_VALUE

async def edit_price_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new price input and update database"""
    new_price = update.message.text.strip()
    price_type = context.user_data.get('price_type')
    
    if not new_price:
        await update.message.reply_text("❌ Price cannot be empty. Try again:")
        return EDIT_PRICE_VALUE
    
    # Update database
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Settings).where(Settings.id == 1))
        settings = result.scalar_one()
        
        if price_type == "individual":
            settings.individual_price = new_price
        else:
            settings.couple_price = new_price
        
        await session.commit()
    
    await update.message.reply_text(
        f"✅ <b>Price Updated</b>\n\n"
        f"Type: {price_type.capitalize()}\n"
        f"New Price: {new_price}",
        parse_mode="HTML"
    )
    
    # Clear context
    context.user_data.pop('price_type', None)
    
    return ConversationHandler.END

# ============================================================================
# REQUEST MANAGEMENT (from previous refactor)
# ============================================================================

async def build_request_detail(session, req_id):
    """Fetch request and negotiation history, build formatted detail text"""
    result = await session.execute(select(Request).where(Request.id == req_id))
    req = result.scalar_one_or_none()
    if not req:
        return None, None
    
    # Fetch negotiation history
    hist_result = await session.execute(
        select(Negotiation).where(Negotiation.request_id == req_id).order_by(Negotiation.timestamp)
    )
    history = hist_result.scalars().all()
    
    # Build detail text
    detail_text = (
        f"<b>Request UUID:</b> <code>{req.request_uuid}</code>\n"
        f"<b>Type:</b> {req.type.value}\n"
        f"<b>User ID:</b> {req.user_id}\n"
        f"<b>Timezone:</b> {req.timezone or 'N/A'}\n"
        f"<b>Desired Time:</b> {req.desired_time or 'N/A'}\n"
        f"<b>Problem:</b> {req.problem or 'N/A'}\n"
        f"<b>Status:</b> {req.status.value}\n"
        f"<b>Final Time:</b> {req.final_time or 'N/A'}\n\n"
        "<b>Negotiation History:</b>\n"
    )
    if history:
        for h in history:
            sender = "Admin" if h.sender == SenderType.ADMIN else "Client"
            detail_text += f"{sender} ({h.timestamp.strftime('%Y-%m-%d %H:%M')}): {h.message}\n"
    else:
        detail_text += "No messages yet.\n"
    
    return req, detail_text

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main router for admin callback actions"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    parts = data.split('_')
    if len(parts) < 3:
        await query.edit_message_text("Invalid callback data.")
        return
    
    action = parts[1]  # view, approve, reject, prop
    req_id = int(parts[2])
    
    # Delegate to specific handler
    if action == "view":
        return await admin_view_request(query, context, req_id)
    elif action == "approve":
        return await admin_approve_request(query, context, req_id)
    elif action == "reject":
        return await admin_reject_request(query, context, req_id)
    else:
        await query.edit_message_text(f"Unknown action: {action}")

async def admin_view_request(query, context, req_id):
    """Display request details with action buttons"""
    async with AsyncSessionLocal() as session:
        req, detail_text = await build_request_detail(session, req_id)
        if not req:
            await query.edit_message_text("Request not found.")
            return
        
        # Action buttons (only for pending/negotiating)
        btns = []
        if req.status in [RequestStatus.PENDING, RequestStatus.NEGOTIATING]:
            btns.append([
                InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{req.id}"),
                InlineKeyboardButton("💬 Propose Alt", callback_data=f"adm_prop_{req.id}")
            ])
            btns.append([
                InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{req.id}")
            ])
        
        await query.edit_message_text(
            detail_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns) if btns else None
        )

async def admin_approve_request(query, context, req_id):
    """Approve request and notify user"""
    async with AsyncSessionLocal() as session:
        req, detail_text = await build_request_detail(session, req_id)
        if not req:
            await query.edit_message_text("Request not found.")
            return
        
        # Update status
        req.status = RequestStatus.CONFIRMED
        req.final_time = req.desired_time or req.final_time
        await session.commit()
        
        # Get user language
        user_lang = await get_user_language(req.user_id)
        
        # Notify user
        user_msg = get_text(user_lang, "status_confirmed") + f"\n{get_text(user_lang, 'negotiation_agreed', time=req.final_time or 'TBD')}"
        try:
            await context.bot.send_message(req.user_id, user_msg)
        except Exception as e:
            print(f"Failed to notify user {req.user_id}: {e}")
        
        # Update admin view
        await query.edit_message_text(
            detail_text + "\n\n✅ <b>CONFIRMED</b>",
            parse_mode="HTML"
        )

async def admin_reject_request(query, context, req_id):
    """Reject request and notify user"""
    async with AsyncSessionLocal() as session:
        req, detail_text = await build_request_detail(session, req_id)
        if not req:
            await query.edit_message_text("Request not found.")
            return
        
        # Update status
        req.status = RequestStatus.REJECTED
        await session.commit()
        
        # Get user language
        user_lang = await get_user_language(req.user_id)
        
        # Notify user
        try:
            await context.bot.send_message(
                req.user_id, 
                get_text(user_lang, "negotiation_rejected")
            )
        except Exception as e:
            print(f"Failed to notify user {req.user_id}: {e}")
        
        # Update admin view
        await query.edit_message_text(
            detail_text + "\n\n❌ <b>REJECTED</b>",
            parse_mode="HTML"
        )

async def admin_propose_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start admin proposal conversation"""
    query = update.callback_query
    await query.answer()
    
    # Extract req_id from callback data (format: adm_prop_{req_id})
    req_id = int(query.data.split('_')[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Request).where(Request.id == req_id))
        req = result.scalar_one_or_none()
        if not req:
            await query.edit_message_text("Request not found.")
            return ConversationHandler.END
        
        context.user_data['negotiate_req_id'] = req_id
        await query.message.reply_text("?? Enter alternative time/proposal:")
        return "ADMIN_PROPOSE"

async def admin_propose_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin's proposal text input"""
    req_id = context.user_data.get('negotiate_req_id')
    if not req_id:
        await update.message.reply_text("Error: No active negotiation found.")
        return ConversationHandler.END
    
    text = update.message.text
    async with AsyncSessionLocal() as session:
        # Log negotiation
        neg = Negotiation(request_id=req_id, sender=SenderType.ADMIN, message=text)
        session.add(neg)
        
        result = await session.execute(select(Request).where(Request.id == req_id))
        req = result.scalar_one_or_none()
        if not req:
            await update.message.reply_text("Error: Request not found.")
            return ConversationHandler.END
        
        req.status = RequestStatus.NEGOTIATING
        await session.commit()
        
        # Get user language
        user_lang = await get_user_language(req.user_id)
        
        # Send to User with action buttons
        btns = [
            [InlineKeyboardButton(get_text(user_lang, "btn_agree"), callback_data=f"usr_yes_{req_id}")],
            [InlineKeyboardButton(get_text(user_lang, "btn_counter"), callback_data=f"usr_counter_{req_id}")]
        ]
        msg = get_text(user_lang, "negotiation_new", msg=text)
        
        try:
            await context.bot.send_message(
                req.user_id, 
                msg, 
                reply_markup=InlineKeyboardMarkup(btns)
            )
        except Exception as e:
            print(f"Failed to send proposal to user {req.user_id}: {e}")
            await update.message.reply_text(f"⚠️ Error sending to user: {e}")
            return ConversationHandler.END
    
    await update.message.reply_text("✅ Proposal sent to user.")
    return ConversationHandler.END
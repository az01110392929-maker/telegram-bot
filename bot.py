import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8626819929:AAG3Q_0oxkgIZP_IYnmLtU7bK40v7JM7pfU"
WHATSAPP_NUMBER = "201000744741"

CATEGORIES = {
    "cat_abayat": "عبايات واستقبال",
    "cat_pajamas": "بيجامات وترنجات بيتي",
    "cat_lingerie": "لانجري وشورتات",
    "cat_plussize": "مقاسات خاصة (Plus Size)",
    "cat_casual": "ملابس خروج وكاجوال"
}

user_carts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_carts[user_id] = []
    
    keyboard = [
        [InlineKeyboardButton(f"👗 {name}", callback_data=key)] for key, name in CATEGORIES.items()
    ]
    keyboard.append([InlineKeyboardButton("🛒 عرض سلة الطلبات وتأكيد الأوردر", callback_data="view_cart")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "مرحباً بك في **متجر الجملة للملابس - بورسعيد** 🛍️✨\n\n"
        "اختر القسم لتصفح الموديلات وطلب كميات الجملة:"
    )
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_name = CATEGORIES.get(query.data, "القسم")
    
    text = (
        f"📂 **قسم: {category_name}**\n\n"
        "لطلب موديل بالجملة من هذا القسم، أرسل رسالة تحتوي على:\n"
        "**(كود الموديل / اسمه - عدد الدست أو القطع - المقاسات/الألوان المطلوبة)**\n\n"
        "مثال: `موديل 105 - 2 دستة - ألوان مشكلة`"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="main_menu")],
        [InlineKeyboardButton("🛒 عرض السلة", callback_data="view_cart")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    item_text = update.message.text
    
    if user_id not in user_carts:
        user_carts[user_id] = []
    
    user_carts[user_id].append(item_text)
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة موديل آخر", callback_data="main_menu")],
        [InlineKeyboardButton("✅ تأكيد وإرسال للواتساب", callback_data="view_cart")]
    ]
    await update.message.reply_text(
        f"✅ تم إضافة: \n`{item_text}` إلى سلة طلباتك!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    cart = user_carts.get(user_id, [])
    
    if not cart:
        keyboard = [[InlineKeyboardButton("🔙 اختيار منتجات", callback_data="main_menu")]]
        await query.message.edit_text("🛒 سلتك فارغة حالياً. اختر قسماً وأضف موديلات.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    items_list = "\n".join([f"- {item}" for item in cart])
    summary_text = (
        "📋 **ملخص طلب الجملة:**\n\n"
        f"{items_list}\n\n"
        "اضغط على الزر بالأسفل لإرسال الأوردر مباشرة عبر واتساب لتأكيد الحجز وتحديد طريقة الشحن 👇"
    )
    
    wa_message = f"مرحباً متجر الجملة بورسعيد، أود تأكيد طلب الجملة التالي:\n\n{items_list}"
    encoded_message = urllib.parse.quote(wa_message)
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_message}"
    
    keyboard = [
        [InlineKeyboardButton("📲 إرسال الطلب عبر واتساب", url=wa_link)],
        [InlineKeyboardButton("➕ إضافة أصناف أخرى", callback_data="main_menu")],
        [InlineKeyboardButton("🗑️ تفريغ السلة", callback_data="clear_cart")]
    ]
    await query.message.edit_text(summary_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_carts[update.effective_user.id] = []
    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
    await query.message.edit_text("تم تفريغ السلة بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    for cat_key in CATEGORIES.keys():
        app.add_handler(CallbackQueryHandler(handle_category, pattern=f"^{cat_key}$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_item))
    
    print("البوت يعمل الآن...")
    app.run_polling()

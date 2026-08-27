import os
import re
import html
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === إعدادات البوت والواتساب ===
BOT_TOKEN = "8626819929:AAG3Q_0oxkgIZP_IYnmL4jK9L0M1N2P3Q"
WHATSAPP_NUMBER = "201000744741"

# === الأقسام الافتراضية ===
CATEGORIES = {
    "cat_abayat": "عبايات واستقبال",
    "cat_pajamas": "بيجامات وترنجات بيتي",
    "cat_lingerie": "لانجري وشورتات",
    "cat_plussize": "مقاسات خاصة (Plus Size)",
    "cat_casual": "ملابس خروج وكاجوال"
}

# === هياكل تخزين البيانات المؤقتة ===
user_carts = {}

def get_cart(user_id):
    if user_id not in user_carts:
        user_carts[user_id] = {
            "items": [],
            "state": None,
            "temp_item": None,
            "temp_price": 0.0,
            "temp_code": ""
        }
    return user_carts[user_id]

# === دالة استخراج وتنظيف نصوص المنشورات ===
def parse_post_text(text: str):
    if not text:
        return {"code": "", "price": 0.0, "clean_title": "موديل ملابس"}
    
    clean = re.sub(r'[\u0640]', '', text)
    clean = re.sub(r'[\~_\*`#@]', ' ', clean)
    clean = re.sub(r'[^\w\s\d\.\:\-\/]', ' ', clean)
    clean = ' '.join(clean.split())

    code_match = re.search(r'(?:كود|الكود|موديل|رقم)\s*[:\-]?\s*([A-Za-z0-9\-_]+)', clean)
    code = code_match.group(1) if code_match else ""

    price = 0.0
    price_match = re.search(r'(?:السعر|سعر|جملة|جمله|ج)\s*[:\-]?\s*(\d+(?:\.\d+)?)', clean)
    if not price_match:
        price_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ج|جنيه|جنية|EGP)', clean)
    
    if price_match:
        try:
            price = float(price_match.group(1))
        except ValueError:
            price = 0.0

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0][:40] if lines else "موديل جديد"

    return {
        "code": code,
        "price": price,
        "clean_title": title
    }

# === لوحات التحكم والمفاتيح التفاعلية ===
def get_quantity_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 ربع دسته (3 ق)", callback_data="qty_0.25"),
            InlineKeyboardButton("📦 نص دسته (6 ق)", callback_data="qty_0.5"),
        ],
        [
            InlineKeyboardButton("📦 دسته إلا ربع (9 ق)", callback_data="qty_0.75"),
            InlineKeyboardButton("📦 1 دسته (12 ق)", callback_data="qty_1.0"),
        ],
        [
            InlineKeyboardButton("📦 دسته وربع (15 ق)", callback_data="qty_1.25"),
            InlineKeyboardButton("📦 دسته ونص (18 ق)", callback_data="qty_1.5"),
        ],
        [
            InlineKeyboardButton("📦 2 دسته (24 ق)", callback_data="qty_2.0"),
            InlineKeyboardButton("📦 3 دسته (36 ق)", callback_data="qty_3.0"),
        ],
        [
            InlineKeyboardButton("📦 4 دسته (48 ق)", callback_data="qty_4.0"),
            InlineKeyboardButton("📦 5 دسته (60 ق)", callback_data="qty_5.0"),
        ],
        [InlineKeyboardButton("✍️ كتابة كمية اخري بالدستة", callback_data="custom_qty")],
        [InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="show_catalog")]
    ])

# === الأوامر ومعالجة رسائل البدء والروابط القادمة من القناة ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    cart["state"] = None

    args = context.args if context.args else []
    if args and args[0].startswith("item_"):
        item_code = args[0].replace("item_", "")
        cart["temp_item"] = f"موديل كود {item_code}"
        cart["temp_code"] = item_code
        
        text = f"🛍️ *طلب موديل:* `{item_code}`\n\nاختر الكمية المطلوبة بالجملة:"
        if update.message:
            await update.message.reply_text(text, reply_markup=get_quantity_keyboard(), parse_mode="Markdown")
        return

    items_count = len(cart["items"])
    cart_btn_text = f"🛒 عرض الفاتورة ({items_count} صنف)" if items_count > 0 else "🛒 عرض الفاتورة الحالية"

    welcome_text = (
        "مرحباً بك في متجر الجملة للملابس - شركة بورسعيد 🛍️✨\n\n"
        "يمكنك طلب الموديلات مباشرة واختيار الكميات بالدستة وسنقوم بحساب الإجمالي وإرسال الفاتورة تلقائياً للواتساب."
    )
    
    keyboard = [
        [InlineKeyboardButton("👗 عرض الموديلات والأقسام", callback_data="show_catalog")],
        [InlineKeyboardButton(cart_btn_text, callback_data="show_cart")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

# === معالجة منشورات القناة وتوليد أزرار الطلب التلقائية ===
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post:
        return

    text = post.caption if post.caption else post.text
    if not text:
        return

    parsed = parse_post_text(text)
    bot_username = (await context.bot.get_me()).username
    code_val = parsed['code'] if parsed['code'] else 'auto'
    deep_link = f"https://t.me/{bot_username}?start=item_{code_val}"

    keyboard = [
        [InlineKeyboardButton("🛍️ اطلب هذا الموديل بالجملة", url=deep_link)]
    ]
    
    try:
        if post.caption:
            await post.edit_caption(caption=post.caption, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await post.edit_text(text=post.text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        print(f"Post Update Error: {e}")

# === إدارة الضغط على الأزرار (Callbacks) ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    cart = get_cart(user_id)

    if data == "main_menu":
        await start(update, context)

    elif data == "show_catalog":
        text = "اختر القسم المطلوب لتصفح الموديلات وتحديد الكميات:"
        keyboard = []
        for cat_id, cat_name in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_name}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("cat_"):
        cat_name = data.replace("cat_", "")
        cart["temp_item"] = cat_name
        cart["temp_code"] = ""
        cart["temp_price"] = 0.0

        text = f"📦 القسم المختار: *{cat_name}*\n\nاختر الكمية المطلوبة بالجملة:"
        await query.message.edit_text(text, reply_markup=get_quantity_keyboard(), parse_mode="Markdown")

    elif data.startswith("qty_"):
        qty_val = float(data.replace("qty_", ""))
        item_name = cart.get("temp_item") or "موديل ملابس"
        pieces = int(qty_val * 12)

        cart["items"].append({
            "name": item_name,
            "qty": qty_val,
            "pieces": pieces,
            "code": cart.get("temp_code", ""),
            "price": cart.get("temp_price", 0.0)
        })

        items_count = len(cart["items"])
        text = f"✅ تمت إضافة *{qty_val} دسته* ({pieces} قطعة) من *{item_name}* بنجاح!"
        keyboard = [
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ({items_count} صنف)", callback_data="show_cart")],
            [InlineKeyboardButton("➕ إضافة موديل آخر", callback_data="show_catalog")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "custom_qty":
        cart["state"] = "waiting_custom_qty"
        text = (
            "✍️ *اكتب كمية الدست التي تحتاجها للموديل:*\n"
            "(فوري : من ربع دسته وخصم خاص للكميات)\n"
            "• مثل: *9* أو *10* أو *11* وهكذا العدد الي تحتاجه"
        )
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "show_cart":
        if not cart["items"]:
            text = "🛒 سلة الطلبات فارغة حالياً."
            keyboard = [
                [InlineKeyboardButton("👗 تصفح الموديلات", callback_data="show_catalog")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        summary_lines = []
        total_dozens = 0.0
        total_pieces = 0

        wa_text = "طلب جملة جديد من متجر بورسعيد:\n\n"

        for idx, item in enumerate(cart["items"], 1):
            code_str = f" (كود: {item['code']})" if item.get("code") else ""
            line_desc = f"{idx}. {item['name']}{code_str}: {item['qty']} دسته ({item['pieces']} قطعة)"
            summary_lines.append(line_desc)
            wa_text += f"- {item['name']}{code_str}: {item['qty']} دسته ({item['pieces']} قطعة)\n"
            total_dozens += item["qty"]
            total_pieces += item["pieces"]

        wa_text += f"\n🔢 إجمالي الدست: {total_dozens} دسته\n📦 إجمالي القطع: {total_pieces} قطعة"
        encoded_wa_text = urllib.parse.quote(wa_text)
        wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_wa_text}"

        text = (
            "📋 *تفاصيل الفاتورة والطلب:*\n\n"
            + "\n".join(summary_lines)
            + f"\n\n🔢 *إجمالي الدست:* {total_dozens} دسته"
            + f"\n📦 *إجمالي القطع:* {total_pieces} قطعة"
            + "\n\nاضغط بالأسفل لإرسال الفاتورة عبر الواتساب مباشرة 👇"
        )

        keyboard = [
            [InlineKeyboardButton("📲 إرسال الطلب عبر الواتساب", url=wa_url)],
            [InlineKeyboardButton("➕ إضافة موديل آخر", callback_data="show_catalog")],
            [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "clear_cart":
        cart["items"] = []
        cart["state"] = None
        cart["temp_item"] = None
        text = "🗑️ تم تفريغ الفاتورة بنجاح."
        keyboard = [
            [InlineKeyboardButton("👗 اختيار موديلات جديدة", callback_data="show_catalog")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# === معالجة الرسائل النصية وإدخال الكميات المخصصة ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    text = update.message.text.strip()

    if cart.get("state") == "waiting_custom_qty":
        try:
            qty_val = float(text)
            if qty_val <= 0:
                await update.message.reply_text("يرجى إدخال رقم موجب صحيح أو عشري (مثال: 5 أو 2.5).")
                return

            item_name = cart.get("temp_item") or "موديل ملابس"
            pieces = int(qty_val * 12)

            cart["items"].append({
                "name": item_name,
                "qty": qty_val,
                "pieces": pieces,
                "code": cart.get("temp_code", ""),
                "price": cart.get("temp_price", 0.0)
            })
            cart["state"] = None

            items_count = len(cart["items"])
            msg = f"✅ تمت إضافة *{qty_val} دسته* ({pieces} قطعة) بنجاح!"
            keyboard = [
                [InlineKeyboardButton(f"🛒 عرض الفاتورة ({items_count} صنف)", callback_data="show_cart")],
                [InlineKeyboardButton("➕ إضافة موديل آخر", callback_data="show_catalog")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("عفواً، يرجى كتابة الرقم بالأرقام فقط (مثال: 7 أو 10).")

# === تشغيل البوت وإعدادات الاتصال ===
if __name__ == "__main__":
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(BOT_TOKEN).request(req).get_updates_request(req).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION), handle_channel_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("...البوت يعمل الآن بكفاءة وثبات")
    app.run_polling(poll_interval=1.0, timeout=20)
    

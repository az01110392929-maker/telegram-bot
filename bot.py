import os
import re
import html
import urllib.parse
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === إعدادات البوت والواتساب والقناة ===
BOT_TOKEN = "8834711844:AAHw1VIyzUaU_kQbmm5hsCEmL-XXGuCp59A"
WHATSAPP_NUMBER = "201000744741"
CHANNEL_USERNAME = "Myincom"

CATEGORIES = {
    "cat_abayat": "عبايات واستقبال",
    "cat_pajamas": "بيجامات وترنجات بيتي",
    "cat_lingerie": "لانجري وشورتات",
    "cat_plussize": "مقاسات خاصة (Plus Size)",
    "cat_casual": "ملابس خروج وكاجوال"
}

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

def parse_post_text(text: str):
    if not text:
        return {"code": "موديل", "price": 0.0, "clean_title": "موديل ملابس"}
    
    clean = re.sub(r'[\u0640]', '', text)
    
    code_match = re.search(r'(?:كود|الكود|موديل|رقم)\s*[:\-]?\s*([A-Za-z0-9\-_]+)', clean)
    code = code_match.group(1) if code_match else ""

    price = 0.0
    price_match = re.search(r'(?:السعر|سعر|جملة|جمله|ج)\s*[:\-👉]?\s*(\d+(?:\.\d+)?)', clean)
    if not price_match:
        price_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ج|جنيه|جنية|EGP)', clean)
    if price_match:
        try:
            price = float(price_match.group(1))
        except ValueError:
            price = 0.0

    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("http")]
    title = ""
    for line in lines:
        if any(w in line for w in ["بيجامه", "بجامه", "عبايه", "عباية", "ترنج", "كاش", "سوكيت", "شورت", "طقم", "دفايه"]):
            title = line
            break
    if not title and lines:
        title = lines[0][:40]

    return {
        "code": code if code else "auto",
        "price": price,
        "clean_title": title if title else "موديل جديد"
    }

def get_quantity_keyboard():
    channel_url = f"https://t.me/{CHANNEL_USERNAME}"
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
        [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=channel_url)]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    cart["state"] = None

    args = context.args if context.args else []
    if args and args[0].startswith("item_"):
        item_code = args[0].replace("item_", "")
        item_title = f"موديل {item_code}" if item_code != "auto" else "الموديل المختار"
        cart["temp_item"] = item_title
        cart["temp_code"] = item_code if item_code != "auto" else ""
        
        text = (
            f"🛍️ *تم اختيار الموديل بنجاح!*\n"
            f"🔖 *الكود / الاسم:* `{item_title}`\n\n"
            f"👇 *اختر الكمية المطلوبة بالجملة (بالدستة):*"
        )
        if update.message:
            await update.message.reply_text(text, reply_markup=get_quantity_keyboard(), parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=get_quantity_keyboard(), parse_mode="Markdown")
        return

    items_count = len(cart["items"])
    cart_btn_text = f"🛒 عرض الفاتورة ({items_count} صنف)" if items_count > 0 else "🛒 عرض الفاتورة الحالية"

    welcome_text = (
        "مرحباً بك في متجر الجملة للملابس - شركة بورسعيد 🛍️✨\n\n"
        "يمكنك طلب الموديلات مباشرة من القناة وتحديد الكميات بالدستة وسنقوم بإعداد الفاتورة تلقائياً للواتساب."
    )
    
    keyboard = [
        [InlineKeyboardButton("👗 تصفح الأقسام", callback_data="show_catalog")],
        [InlineKeyboardButton(cart_btn_text, callback_data="show_cart")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

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
        [InlineKeyboardButton("🛍️ تسوق واطلب هذا الموديل", url=deep_link)]
    ]
    
    try:
        if post.caption:
            await post.edit_caption(caption=post.caption, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await post.edit_text(text=post.text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    cart = get_cart(user_id)
    channel_url = f"https://t.me/{CHANNEL_USERNAME}"

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
            [InlineKeyboardButton("↩️ رجوع للقناة لتسوق المزيد", url=channel_url)],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
                [InlineKeyboardButton("👗 تصفح القناة", url=channel_url)],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
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
            [InlineKeyboardButton("↩️ رجوع للقناة لتسوق المزيد", url=channel_url)],
            [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "clear_cart":
        cart["items"] = []
        cart["state"] = None
        cart["temp_item"] = None
        text = "🗑️ تم تفريغ الفاتورة بنجاح."
        keyboard = [
            [InlineKeyboardButton("↩️ تصفح القناة واختيار موديلات", url=channel_url)],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    text = update.message.text.strip()
    channel_url = f"https://t.me/{CHANNEL_USERNAME}"

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
                [InlineKeyboardButton("↩️ رجوع للقناة لتسوق المزيد", url=channel_url)],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("عفواً، يرجى كتابة الرقم بالأرقام فقط (مثال: 7 أو 10).")

def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION), handle_channel_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
            

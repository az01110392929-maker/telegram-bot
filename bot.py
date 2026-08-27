import os
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === البيانات الأساسية ===
BOT_TOKEN = "8626819929:AAG3Q_0oxkgIZP_IYnmL4jK9L0M1N2P3Q"  # تأكد من توكن البوت الخاص بك
WHATSAPP_NUMBER = "201000744741"  # رقم الواتساب بالصيغة الدولية بدون علامة +

# === الأقسام والموديلات ===
CATEGORIES = {
    "cat_abayat": "عبايات واستقبال",
    "cat_pajamas": "بيجامات وترنجات بيتي",
    "cat_lingerie": "لانجري وشورتات",
    "cat_plussize": "مقاسات خاصة (Plus Size)",
    "cat_casual": "ملابس خروج وكاجوال"
}

# === ذاكرة التخزين المؤقتة ===
user_carts = {}

def get_cart(user_id):
    if user_id not in user_carts:
        user_carts[user_id] = {"items": [], "state": None, "temp_item": None}
    return user_carts[user_id]

# === دوال الأوامر والرسائل ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    cart["state"] = None
    cart["temp_item"] = None
    
    welcome_text = (
        "مرحباً بك في متجر الجملة للملابس - شركة بورسعيد 🛍️✨\n\n"
        "يمكنك اختيار الموديل وتحديد الكميات بالدستة وسنقوم بتجهيز الفاتورة وإرسالها مباشرة إلى الواتساب."
    )
    
    keyboard = [
        [InlineKeyboardButton("👗 عرض الموديلات والأقسام", callback_data="show_catalog")],
        [InlineKeyboardButton("🛒 عرض الفاتورة الحالية", callback_data="show_cart")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    cart = get_cart(user_id)

    if data == "main_menu":
        await start(update, context)

    elif data == "show_catalog":
        text = "اختر القسم المطلوب لتحديد الموديل والكمية:"
        keyboard = []
        for cat_id, cat_name in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_name}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("cat_"):
        cat_name = data.replace("cat_", "")
        cart["temp_item"] = cat_name
        
        text = f"📦 القسم المختار: *{cat_name}*\n\nاختر الكمية المطلوبة بالجملة:"
        keyboard = [
            [
                InlineKeyboardButton("ربع دسته (3 ق)", callback_data="qty_0.25"),
                InlineKeyboardButton("نص دسته (6 ق)", callback_data="qty_0.5"),
            ],
            [
                InlineKeyboardButton("دسته إلا ربع (9 ق)", callback_data="qty_0.75"),
                InlineKeyboardButton("1 دسته (12 ق)", callback_data="qty_1.0"),
            ],
            [
                InlineKeyboardButton("دسته وربع (15 ق)", callback_data="qty_1.25"),
                InlineKeyboardButton("دسته ونص (18 ق)", callback_data="qty_1.5"),
            ],
            [
                InlineKeyboardButton("2 دسته (24 ق)", callback_data="qty_2.0"),
                InlineKeyboardButton("3 دسته (36 ق)", callback_data="qty_3.0"),
            ],
            [
                InlineKeyboardButton("4 دسته (48 ق)", callback_data="qty_4.0"),
                InlineKeyboardButton("5 دسته (60 ق)", callback_data="qty_5.0"),
            ],
            [InlineKeyboardButton("✍️ كتابة كمية اخري بالدستة", callback_data="custom_qty")],
            [InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="show_catalog")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("qty_"):
        qty_val = float(data.replace("qty_", ""))
        item_name = cart.get("temp_item", "موديل ملابس")
        pieces = int(qty_val * 12)
        
        cart["items"].append({
            "name": item_name,
            "qty": qty_val,
            "pieces": pieces
        })
        
        text = f"✅ تمت إضافة *{qty_val} دسته* ({pieces} قطعة) من *{item_name}* بنجاح!"
        keyboard = [
            [InlineKeyboardButton("🛒 عرض الفاتورة", callback_data="show_cart")],
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
            summary_lines.append(f"{idx}. {item['name']}: {item['qty']} دسته ({item['pieces']} قطعة)")
            wa_text += f"- {item['name']}: {item['qty']} دسته ({item['pieces']} قطعة)\n"
            total_dozens += item["qty"]
            total_pieces += item["pieces"]
            
        wa_text += f"\nالإجمالي: {total_dozens} دسته ({total_pieces} قطعة)"
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
            
            item_name = cart.get("temp_item", "موديل ملابس")
            pieces = int(qty_val * 12)
            
            cart["items"].append({
                "name": item_name,
                "qty": qty_val,
                "pieces": pieces
            })
            cart["state"] = None
            
            msg = f"✅ تمت إضافة *{qty_val} دسته* ({pieces} قطعة) بنجاح!"
            keyboard = [
                [InlineKeyboardButton("🛒 عرض الفاتورة", callback_data="show_cart")],
                [InlineKeyboardButton("➕ إضافة موديل آخر", callback_data="show_catalog")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("عفواً، يرجى كتابة الرقم بالأرقام فقط (مثال: 7 أو 10).")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("البوت قيد التشغيل...")
    app.run_polling()

if __name__ == "__main__":
    main()
    

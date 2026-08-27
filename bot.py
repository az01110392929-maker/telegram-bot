import os
import re
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

BOT_TOKEN = "8834711844:AAHhTJods1gDRAtE-pOzZPJmgFMuDeJJHpQ"
WHATSAPP_NUMBER = "201000744741"
CHANNEL_URL = "https://t.me/portsaid_clothing"

CATEGORIES = {
    "cat_abayat": "عبايات واستقبال",
    "cat_pajamas": "بيجامات وترنجات بيتي",
    "cat_lingerie": "لانجري وشورتات",
    "cat_plussize": "مقاسات خاصة",
    "cat_casual": "ملابس كاجوال"
}

user_carts = {}

def get_cart(user_id):
    if user_id not in user_carts:
        user_carts[user_id] = {
            "items": [],
            "state": None,
            "temp_item": "موديل ملابس",
            "temp_code": ""
        }
    return user_carts[user_id]

def get_quantity_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("1 دسته (12 ق)", callback_data="qty_1"),
            InlineKeyboardButton("2 دسته (24 ق)", callback_data="qty_2"),
        ],
        [
            InlineKeyboardButton("3 دسته (36 ق)", callback_data="qty_3"),
            InlineKeyboardButton("4 دسته (48 ق)", callback_data="qty_4"),
        ],
        [
            InlineKeyboardButton("5 دسته (60 ق)", callback_data="qty_5"),
            InlineKeyboardButton("6 دسته (72 ق)", callback_data="qty_6"),
        ],
        [
            InlineKeyboardButton("10 دسته (120 ق)", callback_data="qty_10"),
        ],
        [InlineKeyboardButton("✍️ كتابة كمية أخرى", callback_data="custom_qty")],
        [InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="show_catalog")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    cart["state"] = None

    args = context.args if context.args else []
    if args and args[0].startswith("item_"):
        item_code = args[0].replace("item_", "")
        cart["temp_item"] = f"موديل كود {item_code}"
        cart["temp_code"] = item_code
        
        text = f"🛍️ طلب موديل كود: {item_code}\n\nاختر الكمية المطلوبة بالدستة:"
        if update.message:
            await update.message.reply_text(text, reply_markup=get_quantity_keyboard())
        return

    items_count = len(cart["items"])
    btn_name = f"🛒 الفاتورة ({items_count} صنف)" if items_count > 0 else "🛒 عرض الفاتورة"

    welcome_text = "أهلاً بك في متجر الجملة للملابس 🛍️\nاختر من القائمة للبدء بالطلب:"
    
    keyboard = [
        [InlineKeyboardButton("👗 تصفح الأقسام والموديلات", callback_data="show_catalog")],
        [InlineKeyboardButton(btn_name, callback_data="show_cart")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
    ]
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    cart = get_cart(user_id)

    if data == "main_menu":
        await start(update, context)

    elif data == "show_catalog":
        text = "اختر القسم المطلوب:"
        keyboard = []
        for cat_id, cat_name in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_name}")])
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("cat_"):
        cat_name = data.replace("cat_", "")
        cart["temp_item"] = cat_name
        cart["temp_code"] = ""

        text = f"القسم: {cat_name}\nاختر الكمية المطلوبة بالدستة:"
        await query.message.edit_text(text, reply_markup=get_quantity_keyboard())

    elif data.startswith("qty_"):
        qty_val = int(data.replace("qty_", ""))
        item_name = cart.get("temp_item", "موديل ملابس")
        pieces = qty_val * 12

        cart["items"].append({
            "name": item_name,
            "qty": qty_val,
            "pieces": pieces,
            "code": cart.get("temp_code", "")
        })

        items_count = len(cart["items"])
        text = f"✅ تم إضافة {qty_val} دسته ({pieces} قطعة) بنجاح."
        
        keyboard = [
            [InlineKeyboardButton(f"🛒 الفاتورة ({items_count} صنف)", callback_data="show_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة", url=CHANNEL_URL)]
        ]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "custom_qty":
        cart["state"] = "waiting_custom_qty"
        await query.message.reply_text("✍️ أرسل عدد الدست المطلوب كأرقام فقط (مثال: 8):")

    elif data == "show_cart":
        if not cart["items"]:
            text = "سلة الفاتورة فارغة."
            keyboard = [
                [InlineKeyboardButton("👗 تصفح الأقسام", callback_data="show_catalog")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        lines = []
        total_d = 0
        total_p = 0
        wa_text = "طلب جملة جديد:\n\n"

        for idx, item in enumerate(cart["items"], 1):
            c_txt = f" (كود {item['code']})" if item['code'] else ""
            line = f"{idx}. {item['name']}{c_txt}: {item['qty']} دسته ({item['pieces']} ق)"
            lines.append(line)
            wa_text += f"- {item['name']}{c_txt}: {item['qty']} دسته ({item['pieces']} ق)\n"
            total_d += item["qty"]
            total_p += item["pieces"]

        wa_text += f"\nإجمالي الدست: {total_d}\nإجمالي القطع: {total_p}"
        wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(wa_text)}"

        text = (
            "📋 محتويات الفاتورة:\n\n"
            + "\n".join(lines)
            + f"\n\n🔢 إجمالي الدست: {total_d}"
            + f"\n📦 إجمالي القطع: {total_p}"
        )

        keyboard = [
            [InlineKeyboardButton("📲 إرسال الطلب عبر الواتساب", url=wa_url)],
            [InlineKeyboardButton("🔙 رجوع للقناة", url=CHANNEL_URL)],
            [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "clear_cart":
        cart["items"] = []
        cart["state"] = None
        cart["temp_item"] = "موديل ملابس"
        cart["temp_code"] = ""
        text = "تم تفريغ الفاتورة."
        keyboard = [
            [InlineKeyboardButton("👗 اختيار موديلات", callback_data="show_catalog")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = get_cart(user_id)
    text = update.message.text.strip()

    if cart.get("state") == "waiting_custom_qty":
        try:
            qty_val = int(text)
            if qty_val <= 0:
                await update.message.reply_text("يرجى كتابة رقم صحيح أكبر من صفر.")
                return

            item_name = cart.get("temp_item", "موديل ملابس")
            pieces = qty_val * 12

            cart["items"].append({
                "name": item_name,
                "qty": qty_val,
                "pieces": pieces,
                "code": cart.get("temp_code", "")
            })
            cart["state"] = None

            items_count = len(cart["items"])
            msg = f"✅ تم إضافة {qty_val} دسته ({pieces} قطعة) بنجاح."
            
            keyboard = [
                [InlineKeyboardButton(f"🛒 الفاتورة ({items_count} صنف)", callback_data="show_cart")],
                [InlineKeyboardButton("🔙 رجوع للقناة", url=CHANNEL_URL)]
            ]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        except ValueError:
            await update.message.reply_text("يرجى إرسال أرقام فقط (مثال: 5).")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    

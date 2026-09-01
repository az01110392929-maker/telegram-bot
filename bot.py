import logging
import re
import urllib.parse
import json
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8825183383:AAHWAsREVpdk0j0p497nhF-FcNIVd68iQ"
BOT_USERNAME = "@PorSeuid_Store_Bot"
WHATSAPP_NUMBER = "20100066741"
DEFAULT_CHANNEL_LINK = "https://t.me/clothing10"

DB_FILE = "products.db"

# إعداد قاعدة البيانات السحابية / المحلية المستقرة
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            message_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            unit_price REAL,
            doz_price REAL,
            min_qty INTEGER,
            has_piece_price INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carts (
            user_id INTEGER,
            message_id INTEGER,
            qty INTEGER,
            PRIMARY KEY (user_id, message_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_product(message_id, channel_id, unit_price, doz_price, min_qty, has_piece_price):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO products (message_id, channel_id, unit_price, doz_price, min_qty, has_piece_price)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (message_id, channel_id, unit_price, doz_price, min_qty, int(has_piece_price)))
    conn.commit()
    conn.close()

def get_product(message_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT message_id, channel_id, unit_price, doz_price, min_qty, has_piece_price FROM products WHERE message_id = ?', (message_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "message_id": row[0],
            "channel_id": row[1],
            "unit_price": row[2],
            "doz_price": row[3],
            "min_qty": row[4],
            "has_piece_price": bool(row[5])
        }
    return None

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

user_state = {}
sent_delete_messages = {}

def clean_str(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("#", " ").strip()

def parse_post_text(text):
    text_clean = clean_str(text)
    lines = [l.strip() for l in text_clean.split("\n") if l.strip()]
    if not lines:
        return None

    title = lines[0]
    unit_price = 0.0
    doz_price = 0.0
    has_piece_price = False

    for l in lines:
        cl = clean_str(l)
        if "سعر" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d:
                val = float(d[0])
                if "قطعه" in cl or "قطعة" in cl:
                    unit_price = val
                    has_piece_price = True
                elif "دسته" in cl or "دستة" in cl:
                    doz_price = val

    if doz_price > 0 and unit_price == 0:
        unit_price = round(doz_price / 12, 2)
    elif unit_price > 0 and doz_price == 0:
        doz_price = round(unit_price * 12, 2)

    min_qty = 3
    if "دستة بالجملة" in text_clean or "دسته بالجملة" in text_clean:
        min_qty = 12
    elif "دستة" in text_clean or "دسته" in text_clean:
        min_qty = 6
    elif "قطع" in text_clean or "قطعة" in text_clean:
        min_qty = 3
    elif has_piece_price and doz_price == 0:
        min_qty = 3

    return {
        "title": title,
        "unit_price": unit_price,
        "doz_price": doz_price,
        "min_qty": min_qty,
        "has_piece_price": has_piece_price
    }

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.edited_channel_post
    if not message:
        return

    text = message.text or message.caption
    if not text:
        return

    parsed = parse_post_text(text)
    if not parsed or (parsed["unit_price"] == 0 and parsed["doz_price"] == 0):
        return

    save_product(
        message_id=message.message_id,
        channel_id=message.chat.id,
        unit_price=parsed["unit_price"],
        doz_price=parsed["doz_price"],
        min_qty=parsed["min_qty"],
        has_piece_price=parsed["has_piece_price"]
    )

    keyboard = [[InlineKeyboardButton("🛍️ تسوق واطلب", url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=p_{message.message_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.info(f"Could not update reply markup: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
        args = context.args
    else:
        user = update.message.from_user
        args = context.args

    if args and args[0].startswith("p_"):
        try:
            msg_id = int(args[0].split("_")[1])
        except ValueError:
            if query:
                await query.edit_message_text("❌ رابط المنتج غير صالح.")
            else:
                await update.message.reply_text("❌ رابط المنتج غير صالح.")
            return

        prod = get_product(msg_id)
        if not prod:
            if query:
                await query.edit_message_text("⚠️ عذراً، هذا الموديل غير موجود أو تم حذفه.")
            else:
                await update.message.reply_text("⚠️ عذراً، هذا الموديل غير موجود أو تم حذفه.")
            return

        min_q = prod["min_qty"]
        buttons = []
        
        if min_q == 12:
            multipliers = [1, 2, 3, 4, 5, 6]
            for m in multipliers:
                total_q = m * 12
                buttons.append([InlineKeyboardButton(f"📦 {m} دستة ({total_q} ق)", callback_data=f"qty_{msg_id}_{total_q}")])
        elif min_q == 6:
            multipliers = [1, 2, 3, 4, 5, 6]
            for m in multipliers:
                total_q = m * 6
                buttons.append([InlineKeyboardButton(f"📦 {m} نص دستة ({total_q} ق)", callback_data=f"qty_{msg_id}_{total_q}")])
        else:
            options = [3, 6, 12, 24, 36, 48]
            row = []
            for q in options:
                row.append(InlineKeyboardButton(f"{q} قطع", callback_data=f"qty_{msg_id}_{q}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)

        buttons.append([InlineKeyboardButton("✍️ كتابة كمية اخري بالدستة", callback_data=f"customdoz_{msg_id}")])
        buttons.append([InlineKeyboardButton("✍️ كتابة كمية اخري بالقطعة", callback_data=f"custompcs_{msg_id}")])
        buttons.append([InlineKeyboardButton("🛒 عرض السلة", callback_data="show_cart")])
        buttons.append([InlineKeyboardButton("🔙 العودة للقناة", url=DEFAULT_CHANNEL_LINK)])

        markup = InlineKeyboardMarkup(buttons)
        text = f"📦 اختر الكمية المطلوبة:"

        if query:
            try:
                await query.edit_message_text(text, reply_markup=markup)
            except Exception:
                await query.message.reply_text(text, reply_markup=markup)
        else:
            await update.message.reply_text(text, reply_markup=markup)
        return

    welcome_text = (
        "مرحباً بك في متجر بورسعيد للملابس الجملة 👗✨\n\n"
        "لطلب أي منتج، تصفح قناتنا واضغط على زر (تسوق واطلب) أسفل أي موديل."
    )
    if query:
        await query.edit_message_text(welcome_text)
    else:
        await update.message.reply_text(welcome_text)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("qty_"):
        parts = data.split("_")
        msg_id = int(parts[1])
        qty = int(parts[2])

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO carts (user_id, message_id, qty)
            VALUES (?, ?, ?)
        ''', (user_id, msg_id, qty))
        conn.commit()
        conn.close()

        await query.message.reply_text(f"✅ تم إضافة الكمية ({qty} قطعة) إلى السلة بنجاح!")
        return

    if data == "show_cart":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT message_id, qty FROM carts WHERE user_id = ?', (user_id,))
        cart_items = cursor.fetchall()
        conn.close()

        if not cart_items:
            await query.message.reply_text("🛒 سلة المشتريات فارغة حالياً.")
            return

        text = "🛒 *محتويات سلتك الحالية:*\n\n"
        total_price_all = 0
        keyboard = []

        for msg_id, qty in cart_items:
            prod = get_product(msg_id)
            if prod:
                price = (prod["doz_price"] / 12) * qty if prod["doz_price"] > 0 else prod["unit_price"] * qty
                total_price_all += price
                text += f"• كمية: {qty} قطعة - الإجمالي: {price:.2f} ج\n"
                keyboard.append([InlineKeyboardButton(f"❌ حذف منتج ({qty} ق)", callback_data=f"del_cart_{msg_id}")])

        text += f"\n💰 *الإجمالي الكلي:* {total_price_all:.2f} ج"
        keyboard.append([InlineKeyboardButton("✅ تأكيد وإرسال الطلب عبر واتساب", callback_data="checkout_wa")])
        keyboard.append([InlineKeyboardButton("🧹 إفراغ السلة", callback_data="clear_cart")])

        markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("del_cart_"):
        msg_id = int(data.split("_")[2])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM carts WHERE user_id = ? AND message_id = ?', (user_id, msg_id))
        conn.commit()
        conn.close()
        await query.message.reply_text("🗑️ تم حذف المنتج من السلة.")
        return

    if data == "clear_cart":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM carts WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        await query.message.reply_text("🧹 تم إفراغ السلة بنجاح.")
        return

    if data == "checkout_wa":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT message_id, qty FROM carts WHERE user_id = ?', (user_id,))
        cart_items = cursor.fetchall()
        conn.close()

        if not cart_items:
            await query.message.reply_text("🛒 سلتك فارغة.")
            return

        order_text = "السلام عليكم، أود طلب المنتجات الآتية:\n\n"
        total_price_all = 0

        for msg_id, qty in cart_items:
            prod = get_product(msg_id)
            if prod:
                price = (prod["doz_price"] / 12) * qty if prod["doz_price"] > 0 else prod["unit_price"] * qty
                total_price_all += price
                order_text += f"- الكمية: {qty} قطعة (المعرف: {msg_id}) - التكلفة: {price:.2f} ج\n"

        order_text += f"\n💰 *الإجمالي الكلي:* {total_price_all:.2f} ج"
        encoded_text = urllib.parse.quote(order_text)
        wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_text}"

        markup = InlineKeyboardMarkup([[InlineKeyboardButton("📲 إتمام الطلب عبر واتساب", url=wa_url)]])
        await query.message.reply_text("اضغط على الزر أدناه لإرسال طلبك مباشرة عبر واتساب:", reply_markup=markup)
        return

    if data.startswith("customdoz_") or data.startswith("custompcs_") :
        parts = data.split("_")
        mode = parts[0]
        msg_id = int(parts[1])
        user_state[user_id] = {"action": mode, "msg_id": msg_id}
        unit_label = "دستة" if "doz" in mode else "قطعة"
        await query.message.reply_text(f"✍️ من فضلك اكتب الكمية المطلوبة بـ ({unit_label}) في رسالة وسائط أو نصية الآن:")
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_state:
        return

    state = user_state.pop(user_id)
    text = update.message.text
    try:
        val = int(clean_str(text))
    except ValueError:
        await update.message.reply_text("❌ من فضلك أرسل رقماً صحيحاً فقط.")
        return

    msg_id = state["msg_id"]
    qty = val * 12 if "doz" in state["action"] else val

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO carts (user_id, message_id, qty)
        VALUES (?, ?, ?)
    ''', (user_id, msg_id, qty))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ تم إضافة كمية ({qty} قطعة) إلى السلة بنجاح!")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start, pattern="^p_"))
    application.add_handler(CallbackQueryHandler(handle_callback))
    # تم تصحيح الفلتر هنا ليتوافق مع جميع إصدارات المكتبة الحديثة والقديمة
    application.add_handler(MessageHandler(filters.ALL, handle_channel_post))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
    

import logging
import re
import urllib.parse
import json
import os
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8925183383:AAGTkjTAow_vFSjFhNcTtTPgKxDhq2h7Auo"
BOT_USERNAME = "PortSaid_Store_bot"
WHATSAPP_NUMBER = "201000744741"
DEFAULT_CHANNEL_LINK = "https://t.me/Clothing010"

DB_FILE = "products_db.json"
CARTS_FILE = "user_carts.json"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def load_data(p):
    if os.path.exists(p):
        try: return json.load(open(p, "r", encoding="utf-8"))
        except: return {}
    return {}

def save_data(p, d):
    try: json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass

products_db = load_data(DB_FILE)
user_carts = load_data(CARTS_FILE)
user_state = {}

def clean_str(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("#", " ")

def parse_post_text(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return None
    title, unit_price, doz_price = lines[0], 0.0, 0.0
    for l in lines:
        cl = clean_str(l)
        if "سعر" in cl or "دستة" in cl or "دسته" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d: doz_price = float(d[0])
    if doz_price > 0: unit_price = round(doz_price / 12, 2)
    return {"title": title, "price": unit_price, "doz_price": doz_price, "min_qty": 3}

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post or update.edited_channel_post
    if not post: return
    raw = post.caption or post.text or ""
    data = parse_post_text(raw)
    if data:
        pid = str(post.message_id)
        data["photo_id"] = post.photo[-1].file_id if post.photo else None
        if post.chat.username:
            data["link"] = f"https://t.me/{post.chat.username}/{post.message_id}"
        else:
            cid = str(post.chat.id).replace('-100', '')
            data["link"] = f"https://t.me/c/{cid}/{post.message_id}"
        products_db[pid] = data
        save_data(DB_FILE, products_db)
        try:
            await post.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ تسوق واطلب هذا الموديل", url=f"https://t.me/{BOT_USERNAME}?start=buy_{pid}")]]))
        except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, args = str(update.effective_user.id), context.args
    if uid not in user_carts: user_carts[uid] = []
    if args and args[0].startswith("buy_"):
        pid = args[0].replace("buy_", "")
        p = products_db.get(pid)
        if p:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 ربع (3 ق)", callback_data=f"add_{pid}_3"), InlineKeyboardButton("📦 نص (6 ق)", callback_data=f"add_{pid}_6")],
                [InlineKeyboardButton("📦 دستة إلا ربع (9 ق)", callback_data=f"add_{pid}_9"), InlineKeyboardButton("📦 دستة (12 ق)", callback_data=f"add_{pid}_12")],
                [InlineKeyboardButton("📦 دستة وربع (15 ق)", callback_data=f"add_{pid}_15"), InlineKeyboardButton("📦 دستة ونص (18 ق)", callback_data=f"add_{pid}_18")],
                [InlineKeyboardButton("📦 2 دستة (24 ق)", callback_data=f"add_{pid}_24"), InlineKeyboardButton("📦 3 دستة (36 ق)", callback_data=f"add_{pid}_36")],
                [InlineKeyboardButton("✍️ كتابة كمية اخري", callback_data=f"custom_{pid}")]
            ])
            msg = f"🛍️ <b>الموديل:</b> {html.escape(p['title'])}\n👇 <b>اختر الكمية المطلوبة:</b>"
            if p.get("photo_id"): await update.message.reply_photo(photo=p["photo_id"], caption=msg, reply_markup=kb, parse_mode=ParseMode.HTML)
            else: await update.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
            return
    cnt = len(user_carts.get(uid, []))
    await update.message.reply_text(
        f"مرحباً بك في <b>شركة بورسعيد لاستيراد وتصدير الملابس</b> 🛍️\n🛒 الأصناف في فاتورتك: <b>{cnt}</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ({cnt})", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
        ]),
        parse_mode=ParseMode.HTML
    )

def get_qty_label(qty):
    labels = {
        3: "ربع دستة (3 قطع)",
        6: "نص دستة (6 قطع)",
        9: "دستة إلا ربع (9 قطع)",
        12: "1 دستة (12 قطعة)",
        15: "دستة وربع (15 قطعة)",
        18: "دستة ونصف (18 قطعة)",
        24: "2 دستة (24 قطعة)",
        36: "3 دستة (36 قطعة)"
    }
    if qty in labels: return labels[qty]
    doz = qty / 12
    if doz.is_integer(): return f"{int(doz)} دستة ({qty} قطعة)"
    return f"{doz} دستة ({qty} قطعة)"

async def handle_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, parts = str(update.effective_user.id), query.data.split("_")
    pid, qty = parts[1], int(parts[2])
    p = products_db.get(pid)
    if not p: return
    unit_p = p.get('price', round(p.get('doz_price', 0) / 12, 2))
    tot = int((p.get('doz_price', unit_p*12) / 12) * qty)
    label = get_qty_label(qty)
    p_link = p.get("link", DEFAULT_CHANNEL_LINK)
    if uid not in user_carts: user_carts[uid] = []
    user_carts[uid].append({"title": p['title'], "qty": qty, "label": label, "price": unit_p, "total": tot, "link": p_link})
    save_data(CARTS_FILE, user_carts)
    await query.message.reply_text(
        f"✅ تمت إضافة {label} بنجاح!\nالإجمالي: {tot} ج.م",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 عرض الفاتورة", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
        ])
    )

async def custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, pid = str(update.effective_user.id), query.data.replace("custom_", "")
    p = products_db.get(pid)
    if not p: return
    user_state[uid] = {"product": p}
    await query.message.reply_text("✍️ اكتب الكمية المطلوبة أرقاماً (مثل: 3 أو 4 أو 2.5):")

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in user_state:
        p = user_state[uid]["product"]
        txt = clean_str(update.message.text.strip())
        try: doz = float(re.findall(r'\d+(?:\.\d+)?', txt)[0])
        except: 
            await update.message.reply_text("⚠️ أدخل رقماً صحيحاً.")
            return
        qty = int(doz * 12)
        unit_p = p.get('price', round(p.get('doz_price', 0) / 12, 2))
        tot = int((p.get('doz_price', unit_p*12) / 12) * qty)
        label = get_qty_label(qty)
        p_link = p.get("link", DEFAULT_CHANNEL_LINK)
        if uid not in user_carts: user_carts[uid] = []
        user_carts[uid].append({"title": p['title'], "qty": qty, "label": label, "price": unit_p, "total": tot, "link": p_link})
        save_data(CARTS_FILE, user_carts)
        user_state.pop(uid, None)
        await update.message.reply_text(
            f"✅ تمت إضافة {label} بنجاح!\nالإجمالي: {tot} ج.م",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 عرض الفاتورة", callback_data="view_cart")],
                [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
            ])
        )

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    cart = user_carts.get(uid, [])
    if not cart:
        await query.message.reply_text(
            "🛒 الفاتورة فارغة.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
        )
        return
    
    lines_wa = []
    tot_sum = 0
    for i, it in enumerate(cart, 1):
        pi = f" (القطعة: {it['price']}ج)" if it.get('price', 0) > 0 else ""
        ti = f" = {it['total']}ج" if it.get('total', 0) > 0 else ""
        lines_wa.append(f"{i}. {it['title']}\n📦 الكمية: {it['label']}{pi}{ti}\n🖼️ رابط: {it['link']}")
        tot_sum += it.get('total', 0)
        
    tot_txt = f"\n\n💰 إجمالي الفاتورة الكلي: {tot_sum} ج.م" if tot_sum > 0 else ""
    wa_msg = f"مرحباً شركة بورسعيد لاستيراد وتصدير الملابس، أود تأكيد طلب الجملة التالي:\n\n" + "\n\n".join(lines_wa) + tot_txt
    wa = urllib.parse.quote(wa_msg)
    
    txt = "📋 <b>فاتورة الطلبات:</b>\n\n" + "\n".join([f"{i}. {it['title']} - {it['label']} = {it['total']}ج" for i, it in enumerate(cart, 1)]) + f"\n\n<b>الإجمالي الكلي:</b> {tot_sum} ج.م"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 إرسال عبر واتساب", url=f"https://wa.me/{WHATSAPP_NUMBER}?text={wa}")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear")],
        [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
    ])
    await query.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    user_carts[uid] = []
    save_data(CARTS_FILE, user_carts)
    await query.message.reply_text(
        "تم تفريغ الفاتورة ✅",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear, pattern="^clear$"))
    app.add_handler(CallbackQueryHandler(handle_qty, pattern="^add_"))
    app.add_handler(CallbackQueryHandler(custom_qty, pattern="^custom_"))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, msg_handler))
    app.run_polling()
    

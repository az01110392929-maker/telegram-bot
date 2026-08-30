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
sent_delete_messages = {}

def clean_str(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("#", " ")

def parse_post_text(text):
    text_clean = clean_str(text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return None
    
    title = lines[0]
    unit_price = 0.0
    doz_price = 0.0
    has_piece_price = False
    
    for l in lines:
        cl = clean_str(l)
        if "سعر القطعه" in cl or "سعر القطعة" in cl or ("القطعه" in cl and "سعر" in cl) or ("القطعة" in cl and "سعر" in cl) or ("يعني" in cl and "القطعه" in cl) or ("يعنى" in cl and "القطعه" in cl):
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d:
                unit_price = float(d[0])
                has_piece_price = True
        elif "سعر الدسته" in cl or "سعر الدستة" in cl or "الدسته" in cl or "دستة" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d and doz_price == 0: doz_price = float(d[0])

    if doz_price > 0 and unit_price == 0:
        unit_price = round(doz_price / 12, 2)
    elif unit_price > 0 and doz_price == 0:
        doz_price = round(unit_price * 12, 2)

    min_qty = 3
    if "من اول دسته" in text_clean or "من اول دستة" in text_clean:
        min_qty = 12
    elif "نص دسته" in text_clean or "نصف دسته" in text_clean or "نص دستة" in text_clean:
        min_qty = 6
    elif "ربع دسته" in text_clean or "ربع دستة" in text_clean:
        min_qty = 3
    elif has_piece_price and doz_price == 0:
        min_qty = 3
    elif doz_price > 0 and not has_piece_price:
        min_qty = 12
    elif "دستة" in text_clean or "دسته" in text_clean:
        if "ربع" not in text_clean and "نص" not in text_clean:
            min_qty = 12

    return {
        "title": title, 
        "price": unit_price, 
        "doz_price": doz_price, 
        "min_qty": min_qty, 
        "has_piece_price": has_piece_price
    }

def generate_quantity_keyboard(pid, min_qty):
    if min_qty >= 12:
        all_options = [
            (12, "📦 دستة (12 ق)"),
            (24, "📦 2 دستة (24 ق)"),
            (36, "📦 3 دستة (36 ق)"),
            (48, "📦 4 دستة (48 ق)"),
            (60, "📦 5 دستة (60 ق)"),
            (72, "📦 6 دستة (72 ق)")
        ]
    elif min_qty == 6:
        all_options = [
            (6, "📦 نص (6 ق)"),
            (12, "📦 دستة (12 ق)"),
            (18, "📦 دستة ونص (18 ق)"),
            (24, "📦 2 دستة (24 ق)"),
            (30, "📦 2 دستة ونص (30 ق)"),
            (36, "📦 3 دستة (36 ق)"),
            (42, "📦 3 دستة ونص (42 ق)"),
            (48, "📦 4 دستة (48 ق)")
        ]
    else:
        all_options = [
            (3, "📦 ربع (3 ق)"),
            (6, "📦 نص (6 ق)"),
            (9, "📦 دستة إلا ربع (9 ق)"),
            (12, "📦 دستة (12 ق)"),
            (15, "📦 دستة وربع (15 ق)"),
            (18, "📦 دستة ونص (18 ق)"),
            (24, "📦 2 دستة (24 ق)"),
            (27, "📦 2 دستة وربع (27 ق)"),
            (30, "📦 2 دستة ونص (30 ق)")
        ]
    
    valid_buttons = [InlineKeyboardButton(label, callback_data=f"add_{pid}_{q}") for q, label in all_options]
    kb = []
    for i in range(0, len(valid_buttons), 2):
        kb.append(valid_buttons[i:i+2])
    kb.append([InlineKeyboardButton("✍️ كتابة كمية اخري بالدستة", callback_data=f"custom_{pid}")])
    return InlineKeyboardMarkup(kb)

async def process_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post or update.edited_channel_post
    if not post: return
    raw = post.caption or post.text or ""
    data = parse_post_text(raw)
    if data:
        chat_id_str = str(post.chat.id).replace('-100', '')
        pid = f"{chat_id_str}_{post.message_id}"
        
        if post.photo:
            data["photo_id"] = post.photo[-1].file_id
            
        if post.chat.username:
            data["link"] = f"https://t.me/{post.chat.username}/{post.message_id}"
        else:
            data["link"] = f"https://t.me/c/{chat_id_str}/{post.message_id}"
            
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
        
        if not p:
            for k, val in products_db.items():
                if pid == k or pid in k or k in pid:
                    p = val
                    pid = k
                    break
                    
        if not p and products_db:
            pid = list(products_db.keys())[-1]
            p = products_db.get(pid)
            
        if p:
            user_state[uid] = {"active_pid": pid}
            min_q = p.get('min_qty', 3)
            min_pieces = min_q if min_q >= 3 else 3
            
            kb = generate_quantity_keyboard(pid, min_q)
            msg = f"🛍️ <b>الموديل:</b> {html.escape(p['title'])}\nالحد الأدنى للطلب : {min_pieces} قطع\n👇 <b>اختر الكمية المطلوبة:</b>"
            
            if p.get("photo_id"): 
                await update.message.reply_photo(photo=p["photo_id"], caption=msg, reply_markup=kb, parse_mode=ParseMode.HTML)
            else: 
                await update.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

    cnt = len(user_carts.get(uid, []))
    await update.message.reply_text(
        f"مرحباً بك في <b>شركة بورسعيد لاستيراد وتصدير الملابس</b> 🛍️\n🛒 الأصناف في فاتورتك: <b>{cnt}</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ({cnt} صنف)", callback_data="view_cart")],
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
        18: "دستة ونص (18 قطعة)",
        24: "2 دستة (24 قطعة)",
        27: "2 دستة وربع (27 قطعة)",
        30: "2 دستة ونص (30 قطعة)",
        36: "3 دستة (36 قطعة)",
        42: "3.5 دستة (42 قطعة)",
        48: "4 دستة (48 قطعة)",
        60: "5 دستة (60 قطعة)",
        72: "6 دستة (72 قطعة)"
    }
    if qty in labels: return labels[qty]
    doz = qty / 12
    if doz.is_integer(): return f"{int(doz)} دستة ({qty} قطعة)"
    return f"{doz} دستة ({qty} قطعة)"

async def handle_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    data_parts = query.data.split("_")
    qty = int(data_parts[-1])
    pid = "_".join(data_parts[1:-1])
    
    p = products_db.get(pid)
    if not p:
        for k, val in products_db.items():
            if pid == k or pid in k or k in pid:
                p = val
                break
    if not p: return
    
    unit_p = p.get('price', 0)
    has_piece_price = p.get('has_piece_price', False)
    
    doz_p = p.get('doz_price', 0)
    if doz_p > 0:
        tot = int((doz_p / 12) * qty)
    else:
        tot = int(unit_p * qty)

    label = get_qty_label(qty)
    p_link = p.get("link", DEFAULT_CHANNEL_LINK)
    p_photo = p.get("photo_id")
    if uid not in user_carts: user_carts[uid] = []
    
    user_carts[uid].append({
        "title": p['title'], 
        "qty": qty, 
        "label": label, 
        "price": unit_p if has_piece_price else 0, 
        "total": tot, 
        "link": p_link, 
        "photo_id": p_photo
    })
    save_data(CARTS_FILE, user_carts)
    
    if uid in user_state:
        user_state[uid].pop("active_pid", None)

    cnt = len(user_carts[uid])
    await query.message.reply_text(
        f"✅ تمت إضافة {label} بنجاح!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ({cnt} صنف)", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=p_link)]
        ])
    )

async def custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    pid = query.data.replace("custom_", "")
    
    p = products_db.get(pid)
    if not p:
        for k, val in products_db.items():
            if pid == k or pid in k or k in pid:
                p = val
                pid = k
                break
    if not p: return
    
    # تخزين رقم الموديل بدقة مطلقة مرتبطة بزر الكتابة
    user_state[uid] = {"active_pid": pid}
    await query.message.reply_text("✍️ اكتب عدد الدستات المطلوبة (مثل: 4 أو ٤ أو 2.5 أو ٢.٥ أو 4 دسته ونص):")

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    pid = None
    
    if uid in user_state and "active_pid" in user_state[uid]:
        pid = user_state[uid]["active_pid"]
    
    p = products_db.get(pid) if pid else None

    # إذا لم يتم العثور على الموديل النشط بدقة، نأخذ آخر موديل تم التفاعل معه حصراً
    if not p and products_db:
        last_pid = list(products_db.keys())[-1]
        p = products_db.get(last_pid)

    if p:
        txt = clean_str(update.message.text.strip())
        try: 
            d = re.findall(r'\d+(?:\.\d+)?', txt)
            if not d: raise ValueError()
            doz = float(d[0])
            
            if "نص" in txt or "نصف" in txt:
                if doz == int(doz): doz += 0.5
            elif "ربع" in txt:
                if "الا" in txt or "إلا" in txt:
                    if doz == int(doz): doz -= 0.25
                else:
                    if doz == int(doz): doz += 0.25
        except: 
            await update.message.reply_text("⚠️ أدخل رقماً صحيحاً أو عشرياً (مثل: 4 أو 2.5 أو 4 دسته ونص).")
            return

        qty = int(round(doz * 12))
        unit_p = p.get('price', 0)
        has_piece_price = p.get('has_piece_price', False)
        
        doz_p = p.get('doz_price', 0)
        if doz_p > 0:
            tot = int((doz_p / 12) * qty)
        else:
            tot = int(unit_p * qty)

        label = get_qty_label(qty)
        p_link = p.get("link", DEFAULT_CHANNEL_LINK)
        p_photo = p.get("photo_id")
        if uid not in user_carts: user_carts[uid] = []
        
        user_carts[uid].append({
            "title": p['title'], 
            "qty": qty, 
            "label": label, 
            "price": unit_p if has_piece_price else 0, 
            "total": tot, 
            "link": p_link, 
            "photo_id": p_photo
        })
        save_data(CARTS_FILE, user_carts)
        
        if uid in user_state:
            user_state[uid].pop("active_pid", None)
            
        cnt = len(user_carts[uid])
        await update.message.reply_text(
            f"✅ تمت إضافة {label} بنجاح!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🛒 عرض الفاتورة ({cnt} صنف)", callback_data="view_cart")],
                [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=p_link)]
            ])
        )

async def send_cart_view(bot, chat_id, uid):
    cart = user_carts.get(uid, [])
    if not cart:
        await bot.send_message(
            chat_id=chat_id,
            text="🛒 <b>الفاتورة فارغة الآن.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]]),
            parse_mode=ParseMode.HTML
        )
        return
        
    tot_sum = sum(it.get('total', 0) for it in cart)
    last_link = cart[-1].get("link", DEFAULT_CHANNEL_LINK) if cart else DEFAULT_CHANNEL_LINK
    
    summary = f"📋 <b>فاتورة طلبات الجملة ({len(cart)} أصناف):</b>\n\n" + "\n\n".join([f"<b>{i}. {html.escape(it['title'])}</b>\n📦 الكمية: <b>{it['label']}</b>" + (f" (القطعة: {it['price']}ج)" if it.get('price', 0) > 0 else "") + (f" = {it['total']}ج" if it.get('total', 0) > 0 else "") + f"\n🖼️ <a href='{it['link']}'>رابط الموديل</a>" for i, it in enumerate(cart, 1)]) + (f"\n\n💰 <b>إجمالي الفاتورة الكلي:</b> {tot_sum} ج.م" if tot_sum > 0 else "")
    
    has_deleted = user_state.get(uid, {}).get("has_deleted", False)
    del_btn_text = "❌ حذف صنف آخر من الفاتورة" if has_deleted else "❌ حذف صنف من الفاتورة"
    
    keyboard = [
        [InlineKeyboardButton("📲 إرسال الفاتورة عبر واتساب", callback_data="send_wa")],
        [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=last_link)],
        [InlineKeyboardButton(del_btn_text, callback_data="manage_items")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
    ]
    await bot.send_message(chat_id=chat_id, text=summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    if uid in user_state:
        user_state[uid]["has_deleted"] = False
    await send_cart_view(context.bot, update.effective_chat.id, uid)

async def manage_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    cart = user_carts.get(uid, [])
    if not cart:
        await query.message.reply_text("🛒 الفاتورة فارغة.")
        return
    
    if uid in sent_delete_messages:
        for mid in sent_delete_messages[uid]:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
            except: pass
    sent_delete_messages[uid] = []

    m_head = await query.message.reply_text("🗑️ <b>اختر الصنف المراد حذفه بصورته:</b>", parse_mode=ParseMode.HTML)
    sent_delete_messages[uid].append(m_head.message_id)
    
    for idx, it in enumerate(cart, 1):
        p_total = it.get('total', 0)
        price_line = f"\n💰 الإجمالي: {p_total} ج.م" if p_total > 0 else ""
        cap = f"❌ <b>صنف رقم ({idx}):</b> {html.escape(it['title'])}\n📦 <b>الكمية المطلوبة:</b> {it['label']}{price_line}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"❌ حذف هذا الصنف (رقم {idx})", callback_data=f"del_{idx-1}")]])
        
        if it.get("photo_id"):
            m_item = await query.message.reply_photo(photo=it["photo_id"], caption=cap, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            m_item = await query.message.reply_text(cap, reply_markup=kb, parse_mode=ParseMode.HTML)
        sent_delete_messages[uid].append(m_item.message_id)

async def delete_single_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    try: idx = int(query.data.replace("del_", ""))
    except: idx = -1
    
    if uid in sent_delete_messages:
        for mid in sent_delete_messages[uid]:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
            except: pass
        sent_delete_messages[uid] = []
    
    rem_name = ""
    if uid in user_carts and 0 <= idx < len(user_carts[uid]):
        rem = user_carts[uid].pop(idx)
        save_data(CARTS_FILE, user_carts)
        rem_name = rem['title']
    
    if uid not in user_state:
        user_state[uid] = {}
    user_state[uid]["has_deleted"] = True
    
    await query.message.reply_text(f"🗑️ تم حذف ({rem_name}) بنجاح!")
    await send_cart_view(context.bot, update.effective_chat.id, uid)

async def send_wa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    
    cart = list(user_carts.get(uid, []))
    if not cart:
        await query.message.reply_text("🛒 الفاتورة فارغة بالفعل.")
        return
        
    lines_wa = []
    tot_sum = 0
    for i, it in enumerate(cart, 1):
        pi = f" (القطعة: {it['price']}ج)" if it.get('price', 0) > 0 else ""
        ti = f" = {it['total']}ج" if it.get('total', 0) > 0 else ""
        
        if i == 1:
            link_prefix = f"{it['link']}\n\n"
        else:
            link_prefix = ""
            
        lines_wa.append(f"{link_prefix}{i}. {it['title']}\n📦 الكمية: {it['label']}{pi}{ti}\n🖼️ رابط: {it['link']}")
        tot_sum += it.get('total', 0)
        
    tot_txt_wa = f"\n\n💰 إجمالي الفاتورة الكلي: {tot_sum} ج.م" if tot_sum > 0 else ""
    wa_msg = f"مرحباً شركة بورسعيد لاستيراد وتصدير الملابس، أود تأكيد طلب الجملة التالي:\n\n" + "\n\n".join(lines_wa) + tot_txt_wa
    encoded_wa = urllib.parse.quote(wa_msg)
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_wa}"
    
    user_carts[uid] = []
    save_data(CARTS_FILE, user_carts)
    if uid in user_state:
        user_state[uid]["has_deleted"] = False
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📲 اضغط هنا لفتح واتساب وإرسال الفاتورة", url=wa_link)]])
    await query.message.reply_text(
        "✅ <b>تم تجهيز الفاتورة بنجاح! وتفريغ السلة تلقائياً.</b>\n\nاضغط على الزر أدناه لفتح تطبيق الواتساب وإرسال الطلب فوراً:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE=None):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    user_carts[uid] = []
    save_data(CARTS_FILE, user_carts)
    if uid in user_state:
        user_state[uid]["has_deleted"] = False
    kb_empty = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
    await query.message.reply_text("تم تفريغ الفاتورة ✅", reply_markup=kb_empty)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(send_wa, pattern="^send_wa$"))
    app.add_handler(CallbackQueryHandler(manage_items, pattern="^manage_items$"))
    app.add_handler(CallbackQueryHandler(delete_single_item, pattern="^del_\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_qty, pattern="^add_"))
    app.add_handler(CallbackQueryHandler(custom_qty, pattern="^custom_"))
    
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & (filters.PHOTO | filters.TEXT), process_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, msg_hand

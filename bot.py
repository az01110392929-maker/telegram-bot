import logging
import re
import urllib.parse
import sqlite3
import os
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8925183383:AAE1Ukiw96t_fEHQPKhTrAUnKZgBV8xrPeE"
BOT_USERNAME = "PortSaid_Store_bot"
WHATSAPP_NUMBER = "201000744741"
DEFAULT_CHANNEL_LINK = "https://t.me/Clothing010"

DB_NAME = "store.db"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# إنشاء جداول قاعدة البيانات إذا لم تكن موجودة
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            pid TEXT PRIMARY KEY,
            title TEXT,
            price REAL,
            doz_price REAL,
            min_qty INTEGER,
            has_piece_price INTEGER,
            photo_id TEXT,
            link TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carts (
            uid TEXT,
            title TEXT,
            qty INTEGER,
            label TEXT,
            price REAL,
            total REAL,
            link TEXT,
            photo_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# دوال التعامل مع قاعدة البيانات للمنتجات
def get_product(pid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT title, price, doz_price, min_qty, has_piece_price, photo_id, link FROM products WHERE pid = ?', (pid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "title": row[0], "price": row[1], "doz_price": row[2],
            "min_qty": row[3], "has_piece_price": bool(row[4]),
            "photo_id": row[5], "link": row[6]
        }
    return None

def save_product(pid, data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO products (pid, title, price, doz_price, min_qty, has_piece_price, photo_id, link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        pid, data.get("title"), data.get("price"), data.get("doz_price"),
        data.get("min_qty"), int(data.get("has_piece_price", False)),
        data.get("photo_id"), data.get("link")
    ))
    conn.commit()
    conn.close()

def get_all_products():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT pid, title, price, doz_price, min_qty, has_piece_price, photo_id, link FROM products')
    rows = cursor.fetchall()
    conn.close()
    db = {}
    for row in rows:
        db[row[0]] = {
            "title": row[1], "price": row[2], "doz_price": row[3],
            "min_qty": row[4], "has_piece_price": bool(row[5]),
            "photo_id": row[6], "link": row[7]
        }
    return db

# دوال التعامل مع سلة المشتريات في قاعدة البيانات
def get_cart(uid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT title, qty, label, price, total, link, photo_id FROM carts WHERE uid = ?', (str(uid),))
    rows = cursor.fetchall()
    conn.close()
    cart = []
    for row in rows:
        cart.append({
            "title": row[0], "qty": row[1], "label": row[2],
            "price": row[3], "total": row[4], "link": row[5], "photo_id": row[6]
        })
    return cart

def save_cart_item(uid, item):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO carts (uid, title, qty, label, price, total, link, photo_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(uid), item.get("title"), item.get("qty"), item.get("label"),
        item.get("price"), item.get("total"), item.get("link"), item.get("photo_id")
    ))
    conn.commit()
    conn.close()

def clear_user_cart(uid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM carts WHERE uid = ?', (str(uid),))
    conn.commit()
    conn.close()

def remove_cart_item_at(uid, idx):
    cart = get_cart(uid)
    if 0 <= idx < len(cart):
        cart.pop(idx)
        clear_user_cart(uid)
        for item in cart:
            save_cart_item(uid, item)

user_state = {}
sent_delete_messages = {}

def clean_str(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("#", " ").strip()

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
            
        save_product(pid, data)
        try:
            await post.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ تسوق واطلب هذا الموديل", url=f"https://t.me/{BOT_USERNAME}?start=buy_{pid}")]]))
        except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, args = str(update.effective_user.id), context.args
    
    if args and args[0].startswith("buy_"):
        pid = args[0].replace("buy_", "")
        p = get_product(pid)
        
        if not p:
            try:
                parts = pid.split("_")
                if len(parts) == 2:
                    channel_chat_id = int("-100" + parts[0])
                    msg_id = int(parts[1])
                    forwarded = await context.bot.forward_message(chat_id=update.effective_chat.id, from_chat_id=channel_chat_id, message_id=msg_id)
                    raw = forwarded.caption or forwarded.text or ""
                    await forwarded.delete()
                    p = parse_post_text(raw)
                    if p:
                        if forwarded.photo:
                            p["photo_id"] = forwarded.photo[-1].file_id
                        p["link"] = f"https://t.me/c/{parts[0]}/{msg_id}"
                        save_product(pid, p)
            except:
                pass

        if not p:
            target_msg_id = pid.split("_")[-1]
            all_prods = get_all_products()
            for k, val in all_prods.items():
                if pid in k or k in pid or k.endswith(f"_{target_msg_id}"):
                    p = val
                    pid = k
                    break
            
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
        else:
            await update.message.reply_text("⚠️ عذراً، هذا الموديل غير موجود أو تم حذفه.")
            return

    cnt = len(get_cart(uid))
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
    
    p = get_product(pid)
    if not p:
        all_prods = get_all_products()
        for k, val in all_prods.items():
            if pid == k or pid in k or k in k:
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
    
    save_cart_item(uid, {
        "title": p['title'], "qty": qty, "label": label, 
        "price": unit_p if has_piece_price else 0, 
        "total": tot, "link": p_link, "photo_id": p_photo
    })
    
    if uid in user_state:
        user_state[uid].pop("active_pid", None)

    cnt = len(get_cart(uid))
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
    
    p = get_product(pid)
    if not p:
        all_prods = get_all_products()
        for k, val in all_prods.items():
            if pid == k or pid in k or k in pid:
                p = val
                pid = k
                break
    if not p: return
    
    user_state[uid] = {"active_pid": pid}
    await query.message.reply_text("✍️ اكتب عدد الدستات المطلوبة (مثل: 4 أو ٤ أو 2.5 أو ٢.٥ أو 4 دسته ونص):")

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    pid = None
    
    if uid in user_state and "active_pid" in user_state[uid]:
        pid = user_state[uid]["active_pid"]
        user_state[uid].pop("active_pid", None)
    
    p = get_product(pid) if pid else None

    if p:
        txt = clean_str(update.message.text)
        try: 
            d = re.findall(r'\d+(?:\.\d+)?', txt)
            if not d: raise ValueError()
            doz = float(d[0])
            
            if "نص" in txt or "نصف" in txt or "ونص" in txt:
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
        
        save_cart_item(uid, {
            "title": p['title'], "qty": qty, "label": label, 
            "price": unit_p if has_piece_price else 0, 
            "total": tot, "link": p_link, "photo_id": p_photo
        })
            
        cnt = len(get_cart(uid))
        await query.message.reply_text(
            f"✅ تمت إضافة {label} بنجاح!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🛒 عرض الفاتورة ({cnt} صنف)", callback_data="view_cart")],
                [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=p_link)]
            ])
        )

async def send_cart_view(bot, chat_id, uid):
    cart = get_cart(uid)
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
    cart = get_cart(uid)
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
    
    cart = get_cart(uid)
    rem_name = ""
    if 0 <= idx < len(cart):
        rem_name = cart

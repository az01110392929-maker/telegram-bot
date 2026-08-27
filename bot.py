import logging, re, urllib.parse, html, sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8626819929:AAFebq03VxiW6cU_-a_3_Rpy8_-hYr0VhQQ"
BOT_USERNAME = "Mahmoud_mohammed_bot"
WHATSAPP_NUMBER = "201000744741"
DEFAULT_CHANNEL_LINK = "https://t.me/Clothing010"
DB_NAME = "store_bot.db"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# تهيئة قاعدة البيانات المحلية
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        pid TEXT PRIMARY KEY,
        title TEXT,
        price REAL,
        doz_price REAL,
        min_qty INTEGER,
        link TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid TEXT,
        title TEXT,
        qty REAL,
        label TEXT,
        price REAL,
        doz_price REAL,
        total REAL,
        link TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

user_state = {}
last_parsed_product = {}

def clean_str(s):
    s = re.sub(r'(.)\1+', r'\1', s)
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("#", " ")

# دوال المنتجات
def db_save_product(pid, data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO products (pid, title, price, doz_price, min_qty, link)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (str(pid), data['title'], data['price'], data['doz_price'], data['min_qty'], data['link']))
    conn.commit()
    conn.close()

def db_get_product(pid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT title, price, doz_price, min_qty, link FROM products WHERE pid = ?', (str(pid),))
    row = c.fetchone()
    conn.close()
    if row:
        return {'title': row[0], 'price': row[1], 'doz_price': row[2], 'min_qty': row[3], 'link': row[4]}
    return None

# دوال السلة
def db_add_to_cart(uid, item):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO cart_items (uid, title, qty, label, price, doz_price, total, link)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (str(uid), item['title'], item['qty'], item['label'], item['price'], item['doz_price'], item['total'], item['link']))
    conn.commit()
    conn.close()

def db_get_cart(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, title, qty, label, price, doz_price, total, link FROM cart_items WHERE uid = ?', (str(uid),))
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'title': r[1], 'qty': r[2], 'label': r[3], 'price': r[4], 'doz_price': r[5], 'total': r[6], 'link': r[7]} for r in rows]

def db_delete_cart_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM cart_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()

def db_clear_cart(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM cart_items WHERE uid = ?', (str(uid),))
    conn.commit()
    conn.close()

# استخراج نصوص المنشورات
def parse_post_text(text):
    text_nums = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    lines = [l.strip() for l in text_nums.split("\n") if l.strip()]
    if not lines: return None
    title, code, min_qty, unit_price, doz_price = "", "", 3, 0.0, 0.0
    
    code_match = re.search(r'(?:كود|الكود|موديل|Model|model)\s*[:\-]?\s*([A-Za-z0-9\-_]+)', text_nums, flags=re.IGNORECASE)
    if code_match:
        code = f" (كود {code_match.group(1)})"

    keywords = ["شورت", "ماركه", "ماركة", "aisha", "اسم الموديل", "الموديل", "موديل", "كلون", "كولون", "ليجن", "كارينا", "فيزون", "توب", "بادي", "برا", "اندر", "هاف", "شراب", "بجامه", "بيجامه", "بنطلون", "طقم", "عبايه", "كاش", "ترنج", "فستان", "قميص", "كوليكشن", "سوكت"]
    
    for l in lines:
        cl = clean_str(l)
        if any(k in cl.lower() for k in keywords):
            if not title:
                title = re.sub(r'^[\#\s]*(ماركه|ماركة|اسم الموديل|الموديل|كوليكشن|موديل)\s*[:\-\=\👉\👈]*\s*', '', l, flags=re.IGNORECASE).strip()
                break
                
    if not title:
        for l in lines:
            if "فوري" not in clean_str(l):
                title = l
                break
    if not title: title = lines[0]
    title += code
    
    fc = clean_str(text)
    if "ربع دسته" in fc or "ربع دستة" in fc: min_qty = 3
    elif "نص دسته" in fc or "نصف دسته" in fc or "نص دستة" in fc or "نصف دستة" in fc: min_qty = 6
    elif "دسته" in fc or "دستة" in fc: min_qty = 12
    
    for l in lines:
        cl = clean_str(l)
        if "سعر الدسته" in cl or "سعر الدستة" in cl or "الدسته" in cl or "الدستة" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d:
                doz_price = float(d[0])
                break
                
    for l in lines:
        cl = clean_str(l)
        if "القطعه" in cl or "القطعة" in cl or "سعر القطعه" in cl or "سعر القطعة" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d:
                unit_price = float(d[0])
                break

    if unit_price == 0:
        for l in lines:
            cl = clean_str(l)
            if "السعر" in cl or "سعر" in cl:
                d = re.findall(r'\d+(?:\.\d+)?', cl)
                if d and float(d[0]) != doz_price:
                    unit_price = float(d[0])
                    break

    if doz_price > 0 and unit_price == 0:
        unit_price = round(doz_price / 12, 2)
    elif unit_price > 0 and doz_price == 0:
        doz_price = round(unit_price * 12, 2)
        
    return {"title": title[:50], "price": unit_price, "doz_price": doz_price, "min_qty": min_qty}

def calculate_item_total(p, qty):
    if p.get('doz_price', 0) > 0:
        tot = (p['doz_price'] / 12.0) * qty
        return int(round(tot)) if abs(tot - round(tot)) < 0.05 else round(tot, 2)
    elif p.get('price', 0) > 0:
        tot = p['price'] * qty
        return int(round(tot)) if abs(tot - round(tot)) < 0.05 else round(tot, 2)
    return 0

def get_quantity_label(qty):
    labels = {
        3: "ربع دسته (3 قطع)",
        6: "نص دسته (6 قطع)",
        9: "دسته إلا ربع (9 قطع)",
        12: "1 دسته (12 قطعة)",
        15: "دسته وربع (15 قطعة)",
        18: "دسته ونص (18 قطعة)",
        21: "دستتين إلا ربع (21 قطعة)",
        24: "2 دسته (24 قطعة)"
    }
    if qty in labels: return labels[qty]
    doz = int(qty // 12)
    rem = int(qty % 12)
    if rem == 0: return f"{doz} دسته ({int(qty)} قطعة)"
    elif rem == 3: return f"{doz} دسته وربع ({int(qty)} قطعة)"
    elif rem == 6: return f"{doz} دسته ونصف ({int(qty)} قطعة)"
    elif rem == 9: return f"{doz + 1} دسته إلا ربع ({int(qty)} قطعة)"
    return f"{int(qty)} قطعة"

def generate_quantity_keyboard(post_id, min_qty):
    kb = []
    if min_qty >= 12:
        q_list = [(12,"1 دسته"),(24,"2 دسته"),(36,"3 دسته"),(48,"4 دسته"),(60,"5 دسته"),(72,"6 دسته"),(120,"10 دسته")]
    elif min_qty == 6:
        q_list = [(6,"نص دسته"),(12,"1 دسته"),(18,"دسته ونص"),(24,"2 دسته"),(36,"3 دسته"),(48,"4 دسته"),(60,"5 دسته"),(72,"6 دسته")]
    else:
        q_list = [(3,"ربع دسته"),(6,"نص دسته"),(9,"دسته إلا ربع"),(12,"1 دسته"),(15,"دسته وربع"),(18,"دسته ونص"),(24,"2 دسته"),(36,"3 دسته"),(48,"4 دسته"),(60,"5 دسته")]
        
    row = []
    for q, n in q_list:
        if q >= min_qty:
            row.append(InlineKeyboardButton(f"📦 {n} ({q} ق)", callback_data=f"add_{post_id}_{q}"))
            if len(row) == 2: kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("✍️ كتابة كمية اخري بالدستة", callback_data=f"custom_{post_id}")])
    return InlineKeyboardMarkup(kb)

# معالجة منشورات القناة
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_parsed_product
    post = update.channel_post
    if not post: return
    raw = post.caption or post.text or ""
    data = parse_post_text(raw)
    
    pid = str(post.message_id)
    post_link = f"https://t.me/{post.chat.username}/{post.message_id}" if post.chat.username else DEFAULT_CHANNEL_LINK
    
    if data:
        data["link"] = post_link
        last_parsed_product = data
        db_save_product(pid, data)
    elif last_parsed_product: # في حال كان المنشور صورة إضافية في ألبوم
        data = dict(last_parsed_product)
        data["link"] = post_link
        db_save_product(pid, data)
        
    deep_link = f"https://t.me/{BOT_USERNAME}?start=item_{pid}"
    try:
        await post.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ تسوق واطلب هذا الموديل", url=deep_link)]]))
    except Exception as e:
        logging.error(f"Post edit error: {e}")

# أمر البدء واختيار الموديل
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = str(update.effective_user.id)
    args = context.args

    if args and len(args) > 0 and (args[0].startswith("item_") or args[0].startswith("buy_")):
        pid = args[0].replace("item_", "").replace("buy_", "")
        p = db_get_product(pid)
        if not p:
            p = {
                "title": "موديل من القناة",
                "price": 0.0,
                "doz_price": 0.0,
                "min_qty": 3,
                "link": DEFAULT_CHANNEL_LINK
            }

        price_text = f"{p['price']} ج.م للقطعة" if p['price'] > 0 else "سعر خاص للجملة"
        doz_text = f" | سعر الدستة: {p['doz_price']} ج.م" if p['doz_price'] > 0 else ""
        msg = f"🛍️ <b>الموديل:</b> {html.escape(p['title'])}\n💵 <b>السعر:</b> {price_text}{doz_text}\n📦 <b>الحد الأدنى للطلب:</b> {p['min_qty']} قطع\n\n👇 <b>اختر الكمية المطلوبة:</b>"
        
        await update.message.reply_text(msg, reply_markup=generate_quantity_keyboard(pid, p['min_qty']), parse_mode=ParseMode.HTML)
        return

    cart = db_get_cart(uid)
    cnt = len(cart)
    await update.message.reply_text(
        f"مرحباً بك في <b>متجر الجملة</b> 🛍️\n🛒 الأصناف في فاتورتك: <b>{cnt} صنف</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ( {cnt} صنف )", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
        ]),
        parse_mode=ParseMode.HTML
    )

# اختيار الكمية بالدستة
async def handle_quantity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    parts = query.data.split("_")
    pid, qty = parts[1], int(parts[2])
    
    p = db_get_product(pid) or {
        "title": "موديل جملة",
        "price": 0.0,
        "doz_price": 0.0,
        "link": DEFAULT_CHANNEL_LINK
    }
    
    tot = calculate_item_total(p, qty)
    lbl = get_quantity_label(qty)
    p_link = p.get("link", DEFAULT_CHANNEL_LINK)
    
    item = {
        "title": p['title'],
        "qty": qty,
        "label": lbl,
        "price": p.get('price', 0.0),
        "doz_price": p.get('doz_price', 0.0),
        "total": tot,
        "link": p_link
    }
    db_add_to_cart(uid, item)
    
    cart = db_get_cart(uid)
    cnt = len(cart)
    await query.message.reply_text(
        f"✅ تمت إضافة <b>{lbl}</b> من <b>{html.escape(p['title'])}</b> بنجاح!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ( {cnt} صنف )", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=p_link)]
        ]),
        parse_mode=ParseMode.HTML
    )

async def ask_custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    pid = query.data.replace("custom_", "")
    p = db_get_product(pid) or {"title": "الموديل المختار", "link": DEFAULT_CHANNEL_LINK}
    user_state[uid] = {"action": "waiting_custom_qty", "product": p}
    await query.message.reply_text(f"✍️ اكتب كمية الدست الي تحتاجه للموديل:\n({html.escape(p['title'])})\n• مثل 9 أو 10 أو 11 وهكذا العدد الي تحتاجه", parse_mode=ParseMode.HTML)

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    state = user_state.get(uid)
    if state and state.get("action") == "waiting_custom_qty":
        txt = clean_str(update.message.text.strip())
        p = state.get("product", {"title": "موديل ملابس", "price": 0.0, "doz_price": 0.0, "link": DEFAULT_CHANNEL_LINK})
        d = re.findall(r'\d+', txt)
        if not d: await update.message.reply_text("⚠️ أدخل رقماً صحيحاً."); return
        qty = int(d[0]) * 12
        tot = calculate_item_total(p, qty)
        lbl = get_quantity_label(qty)
        p_link = p.get("link", DEFAULT_CHANNEL_LINK)
        
        item = {
            "title": p.get('title', 'موديل ملابس'),
            "qty": qty,
            "label": lbl,
            "price": p.get('price', 0.0),
            "doz_price": p.get('doz_price', 0.0),
            "total": tot,
            "link": p_link
        }
        db_add_to_cart(uid, item)
        user_state.pop(uid, None)
        
        cart = db_get_cart(uid)
        cnt = len(cart)
        await update.message.reply_text(
            f"✅ تمت إضافة <b>{lbl}</b> بنجاح!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🛒 عرض الفاتورة ( {cnt} صنف )", callback_data="view_cart")],
                [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=p_link)]
            ]),
            parse_mode=ParseMode.HTML
        )

# عرض الفاتورة
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    cart = db_get_cart(uid)

    if not cart:
        kb_empty = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
        await query.message.reply_text("🛒 <b>الفاتورة فارغة الآن.</b>\nيمكنك الرجوع للقناة واختيار الموديلات التي ترغب بها:", reply_markup=kb_empty, parse_mode=ParseMode.HTML)
        return
        
    lines = []
    last_link = cart[-1].get("link", DEFAULT_CHANNEL_LINK) if cart else DEFAULT_CHANNEL_LINK
    for i, it in enumerate(cart, 1):
        pi = f" (القطعة: {it['price']}ج)" if it.get('price', 0) > 0 else ""
        ti = f" = {it['total']}ج" if it.get('total', 0) > 0 else ""
        lines.append(f"<b>{i}. {html.escape(it['title'])}</b>\n📦 الكمية: <b>{it['label']}</b>{pi}{ti}\n🖼️ <a href='{it['link']}'>رابط الموديل في القناة</a>")
        
    tot_sum = sum(it.get('total', 0) for it in cart)
    tot_val = int(tot_sum) if abs(tot_sum - round(tot_sum)) < 0.05 else round(tot_sum, 2)
    tot_txt_html = f"\n\n💰 <b>إجمالي الفاتورة الكلي:</b> {tot_val} ج.م" if tot_sum > 0 else ""
    summary = f"📋 <b>فاتورة طلبات الجملة ({len(cart)} أصناف):</b>\n\n" + "\n\n".join(lines) + tot_txt_html
    
    keyboard = [
        [InlineKeyboardButton("📲 إرسال الفاتورة عبر واتساب", callback_data="send_wa_and_clear")],
        [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=last_link)],
        [InlineKeyboardButton("❌ حذف صنف", callback_data="manage_items")],
        [InlineKeyboardButton("🗑️ تفريغ الفاتورة", callback_data="clear_cart")]
    ]
    await query.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# إرسال الفاتورة عبر واتساب
async def send_wa_and_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    cart = db_get_cart(uid)
    if not cart:
        await query.message.reply_text("🛒 الفاتورة فارغة بالفعل.")
        return
        
    lines_wa, tot_sum = [], 0
    for i, it in enumerate(cart, 1):
        pi = f" (القطعة: {it['price']}ج)" if it.get('price', 0) > 0 else ""
        ti = f" = {it['total']}ج" if it.get('total', 0) > 0 else ""
        item_text = (
            f"*{i}. {it['title']}*\n"
            f"📦 الكمية: {it['label']}{pi}{ti}\n"
            f"🔗 رابط الموديل والصورة: {it['link']}"
        )
        lines_wa.append(item_text)
        tot_sum += it.get('total', 0)
        
    tot_val = int(tot_sum) if abs(tot_sum - round(tot_sum)) < 0.05 else round(tot_sum, 2)
    tot_txt_wa = f"\n\n💰 *إجمالي الفاتورة الكلي:* {tot_val} ج.م" if tot_sum > 0 else ""
    
    wa_msg = (
        "🛍️ *طلب جملة جديد من متجر بورسعيد:*\n"
        "------------------------------------\n\n"
        + "\n\n".join(lines_wa)
        + tot_txt_wa
        + "\n\n------------------------------------\n"
        "يرجى تأكيد الحجز وتجهيز الأوردر."
    )
    
    encoded_wa = urllib.parse.quote(wa_msg)
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_wa}"
    
    db_clear_cart(uid)
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📲 اضغط هنا لفتح الواتساب وإرسال الفاتورة الآن", url=wa_link)]])
    await query.message.reply_text(
        "✅ <b>تم تجهيز الفاتورة وتفريغ السلة بنجاح!</b>\n\nاضغط على الزر أدناه لإرسال الطلب مع روابط الصور والموديلات إلى الواتساب فوراً:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

# إدارة وحذف الأصناف
async def manage_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    cart = db_get_cart(uid)
    if not cart:
        kb_empty = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
        await query.message.reply_text("🛒 <b>الفاتورة فارغة.</b>", reply_markup=kb_empty, parse_mode=ParseMode.HTML)
        return

    await query.message.reply_text("🗑️ <b>اختر الصنف الذي تريد حذفه:</b>", parse_mode=ParseMode.HTML)
    
    for idx, it in enumerate(cart, 1):
        p_price = it.get('price', 0)
        p_doz = it.get('doz_price', round(p_price * 12, 2))
        p_total = it.get('total', 0)
        price_line = ""
        if p_price > 0 or p_doz > 0:
            price_line = f"\n💵 سعر القطعة: {p_price} ج.م | سعر الدستة: {p_doz} ج.م\n💰 إجمالي الصنف: {p_total} ج.م"
            
        cap = f"❌ <b>صنف رقم ({idx}):</b>\n<b>{html.escape(it['title'])}</b>\n📦 الكمية: <b>{it['label']}</b>{price_line}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"❌ حذف هذا الصنف (رقم {idx})", callback_data=f"del_{it['id']}")]])
        await query.message.reply_text(cap, reply_markup=kb, parse_mode=ParseMode.HTML)

async def delete_single_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.replace("del_", ""))
    db_delete_cart_item(item_id)
    await query.message.reply_text("🗑️ تم حذف الصنف بنجاح!")
    await view_cart(update, context)

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE=None):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    db_clear_cart(uid)
    kb_empty = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
    await query.message.reply_text("تم تفريغ الفاتورة بنجاح ✅", reply_markup=kb_empty)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(send_wa_and_clear, pattern="^se

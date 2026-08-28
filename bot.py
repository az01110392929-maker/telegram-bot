import logging, re, urllib.parse, json, os, html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8925183383:AAGTkjTAow_vFSjFhNcTtTPgKxDhq2h7Auo"
BOT_USERNAME = "PortSaid_Store_bot"
WHATSAPP_NUMBER = "201000744741"
DEFAULT_CHANNEL_LINK = "https://t.me/Clothing010"

DB_FILE, CARTS_FILE, CONFIG_FILE, CHANNELS_FILE = "products_db.json", "user_carts.json", "bot_config.json", "user_channels.json"
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def load_data(p):
    return json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else {}
def save_data(p, d):
    try: json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass

products_db = load_data(DB_FILE)
user_carts = load_data(CARTS_FILE)
bot_config = load_data(CONFIG_FILE)
user_last_channel = load_data(CHANNELS_FILE)
user_state = {}
sent_delete_messages = {}

def clean_str(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("#", " ")

def parse_post_text(text):
    text_clean = clean_str(text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return None
    
    title, code, unit_price, doz_price = "", "", 0.0, 0.0
    
    for l in lines:
        cl = clean_str(l)
        if "كود" in cl:
            d = re.findall(r'\d+', l)
            if d: code = f" (كود {d[0]})"
        if any(k in cl for k in ["اسم الموديل", "برا", "اندر", "هاف", "شراب", "بجامه", "بيجامه", "بنطلون", "طقم", "عبايه", "كاش", "ترنج", "فستان", "شورت", "قميص", "كوليكشن", "سوكت", "كلون", "فوري", "إتش", "هوم", "ليجن", "كلوت"]):
            if not title: title = re.sub(r'^[\#\s]*(اسم الموديل|الموديل|كوليكشن|فوري)\s*[:\-\=\👉\👈]*\s*', '', l, flags=re.IGNORECASE).strip()
    if not title: title = lines[0]
    title += code
    
    for l in lines:
        cl = clean_str(l)
        if "سعر الدسته" in cl or ("الدسته" in cl and "سعر" in cl) or "دستة" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d: doz_price = float(d[0])
        elif "سعر القطعه" in cl or ("القطعه" in cl and "سعر" in cl) or "السعر" in cl:
            d = re.findall(r'\d+(?:\.\d+)?', cl)
            if d and doz_price == 0:
                if "دستة" not in cl and "دسته" not in cl:
                    unit_price = float(d[0])

    if unit_price == 0 and doz_price == 0:
        for l in lines:
            cl = clean_str(l)
            if "السعر" in cl or "سعر" in cl:
                d = re.findall(r'\d+(?:\.\d+)?', cl)
                if d:
                    if "دستة" in cl or "دسته" in cl:
                        doz_price = float(d[0])
                    else:
                        unit_price = float(d[0])

    if doz_price > 0 and unit_price == 0:
        unit_price = round(doz_price / 12, 2)
    elif unit_price > 0 and doz_price == 0:
        doz_price = round(unit_price * 12, 2)

    min_qty = 12
    if "ربع دسته" in text_clean or "ربع" in text_clean:
        min_qty = 3
    elif "نص دسته" in text_clean or "نصف دسته" in text_clean or "نص" in text_clean:
        min_qty = 6
    elif "اول دسته" in text_clean or "من اول" in text_clean or "سعر الدسته" in text_clean:
        min_qty = 12
    else:
        if unit_price > 0 and doz_price == 0:
            min_qty = 3
        elif doz_price > 0 and "ربع" not in text_clean and "نص" not in text_clean:
            min_qty = 12

    return {"title": title, "price": unit_price, "doz_price": doz_price, "min_qty": min_qty}

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
        3: "ربع دستة (3 قطع)",
        6: "نص دستة (6 قطع)",
        9: "دستة إلا ربع (9 قطع)",
        12: "1 دستة (12 قطعة)",
        15: "دستة وربع (15 قطعة)",
        18: "دستة ونصف (18 قطعة)",
        21: "دستتين إلا ربع (21 قطعة)",
        24: "2 دستة (24 قطعة)",
        30: "2 دستة ونص (30 قطعه)",
        36: "3 دستة (36 قطعة)",
        42: "3.5 دستة (42 قطعة)",
        48: "4 دستة (48 قطعة)",
        60: "5 دستة (60 قطعة)",
        72: "6 دستة (72 قطعة)"
    }
    if qty in labels:
        return labels[qty]
    doz = qty // 12
    rem = qty % 12
    if rem == 0:
        return f"{doz} دستة ({qty} قطعة)"
    elif rem == 3:
        return f"{doz} دستة وربع ({qty} قطعة)"
    elif rem == 6:
        return f"{doz} دستة ونصف ({qty} قطعة)"
    elif rem == 9:
        return f"{doz + 1} دستة إلا ربع ({qty} قطعة)"
    return f"{qty} قطعة"

def generate_quantity_keyboard(post_id, min_qty):
    kb = []
    if min_qty == 12:
        all_q = [
            (12, "1 دستة"), (24, "2 دستة"), (36, "3 دستة"),
            (48, "4 دستة"), (60, "5 دستة"), (72, "6 دستة")
        ]
    elif min_qty == 6:
        all_q = [
            (6, "نص دستة"), (12, "1 دستة"), (18, "دستة ونصف"),
            (24, "2 دستة"), (30, "2 دستة ونص"), (36, "3 دستة"),
            (48, "4 دستة"), (60, "5 دستة"), (72, "6 دستة")
        ]
    else:
        all_q = [
            (3, "ربع دستة"), (6, "نص دستة"), (9, "دستة إلا ربع"),
            (12, "1 دستة"), (15, "دستة وربع"), (18, "دستة ونصف"),
            (24, "2 دستة"), (30, "2 دستة ونص"), (36, "3 دستة"),
            (42, "3.5 دستة"), (48, "4 دستة"), (60, "5 دستة"), (72, "6 دستة")
        ]
        
    row = []
    for q, n in all_q:
        if q >= min_qty:
            row.append(InlineKeyboardButton(f"📦 {n} ({q} قطعه)" if q == 30 else f"📦 {n} ({q} ق)", callback_data=f"add_{post_id}_{q}"))
            if len(row) == 2: kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("✍️ كتابة كمية اخري بالدستة", callback_data=f"custom_{post_id}")])
    return InlineKeyboardMarkup(kb)

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
            data["channel_base"] = f"https://t.me/{post.chat.username}"
        else:
            cid = str(post.chat.id).replace('-100', '')
            data["link"] = f"https://t.me/c/{cid}/{post.message_id}"
            data["channel_base"] = f"https://t.me/c/{cid}"
        products_db[pid] = data
        save_data(DB_FILE, products_db)
        try:
            await post.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ تسوق واطلب هذا الموديل", url=f"https://t.me/{BOT_USERNAME}?start=buy_{pid}")]]))
        except Exception as e:
            logging.info(f"Could not edit markup for post {pid}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, args = str(update.effective_user.id), context.args
    if uid not in user_carts: user_carts[uid] = []
    
    if args and len(args) > 0 and args[0].startswith("buy_"):
        pid = args[0].replace("buy_", "")
        p = products_db.get(pid)
        if p:
            c_link = p.get("link") or p.get("channel_base")
            if c_link:
                user_last_channel[uid] = c_link
                save_data(CHANNELS_FILE, user_last_channel)

            pt = f"{p['price']} ج.م للقطعة" if p.get('price', 0) > 0 else "حسب المنشور"
            msg = f"🛍️ <b>الموديل:</b> {html.escape(p['title'])}\n💵 <b>السعر:</b> {pt}\n📦 <b>الحد الأدنى للطلب:</b> {p['min_qty']} قطع\n\n👇 <b>اختر الكمية المطلوبة:</b>"
            kb = generate_quantity_keyboard(pid, p['min_qty'])
            if p.get("photo_id"):
                await update.message.reply_photo(photo=p["photo_id"], caption=msg, reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
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

async def handle_quantity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, parts = str(update.effective_user.id), query.data.split("_")
    pid, qty = parts[1], int(parts[2])
    p = products_db.get(pid)
    if not p: return
    
    tot = calculate_item_total(p, qty)
    lbl = get_quantity_label(qty)
    p_link = p.get("link", DEFAULT_CHANNEL_LINK)
    
    if uid not in user_carts: user_carts[uid] = []
    user_carts[uid].append({
        "title": p['title'], "qty": qty, "label": lbl, "price": p['price'],
        "doz_price": p.get('doz_price', round(p['price']*12, 2)), "total": tot, "link": p_link, "photo_id": p.get("photo_id")
    })
    save_data(CARTS_FILE, user_carts)
    await query.message.reply_text(
        f"✅ تمت إضافة <b>{lbl}</b> بنجاح!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 عرض الفاتورة ({len(user_carts[uid])})", callback_data="view_cart")],
            [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
        ]),
        parse_mode=ParseMode.HTML
    )

async def ask_custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, pid = str(update.effective_user.id), query.data.replace("custom_", "")
    p = products_db.get(pid)
    if not p: return
    user_state[uid] = {"action": "waiting_custom_qty", "product": p, "pid": pid}
    await query.message.reply_text(f"✍️ اكتب الكمية المطلوبة للموديل:\n({html.escape(p['title'])})\n• مثل: 6 أو 2.5 أو 3 دستة", parse_mode=ParseMode.HTML)

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    state = user_state.get(uid)
    if state and state.get("action") == "waiting_custom_qty":
        txt = clean_str(update.message.text.strip())
        p = state["product"]
        
        d = re.findall(r'\d+(?:\.\d+)?', txt)
        if not d: 
            await update.message.reply_text("⚠️ أدخل رقماً صحيحاً.")
            return
            
        val = float(d[0])
        if "نص" in txt or "نصف" in txt:
            val += 0.5
        elif "ربع" in txt:
            val += 0.25
        elif "الا ربع" in txt or "إلا ربع" in txt:
            val -= 0.25

        qty = int(round(val * 12))
                
        tot = calculate_item_total(p, qty)
        lbl = get_quantity_label(qty)
        p_link = p.get("link", DEFAULT_CHANNEL_LINK)
        
        if uid not in user_carts: user_carts[uid] = []
        user_carts[uid].append({
            "title": p['title'], "qty": qty, "label": lbl, "price": p['price'],
            "doz_price": p.get('doz_price', round(p['price']*12, 2)), "total": tot, "link": p_link, "photo_id": p.get("photo_id")
        })
        save_data(CARTS_FILE, user_carts)
        user_state.pop(uid, None)
        await update.message.reply_text(
            f"✅ تمت إضافة <b>{lbl}</b> بنجاح!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🛒 عرض الفاتورة", callback_data="view_cart")],
                [InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]
            ]),
            parse_mode=ParseMode.HTML
        )

async def send_cart_view(bot, chat_id, uid, is_after_delete=False):
    cart = user_carts.get(uid, [])
    if not cart:
        kb_empty = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
        await bot.send_message(chat_id=chat_id, text="🛒 <b>الفاتورة فارغة الآن.</b>", reply_markup=kb_empty, parse_mode=ParseMode.HTML)
        return
        
    lines = []
    last_link = cart[-1].get("link", DEFAULT_CHANNEL_LINK) if cart else DEFAULT_CHANNEL_LINK
    for i, it in enumerate(cart, 1):
        pi = f" (القطعة: {it['price']}ج)" if it['price'] > 0 else ""
        ti = f" = {it['total']}ج" if it['total'] > 0 else ""
        lines.append(f"<b>{i}. {html.escape(it['title'])}</b>\n📦 الكمية: <b>{it['label']}</b>{pi}{ti}\n🖼️ <a href='{it['link']}'>رابط الموديل</a>")
        
    tot_sum = sum(it['total'] for it in cart)
    tot_val = int(tot_sum) if abs(tot_sum - round(tot_sum)) < 0.05 else round(tot_sum, 2)
    tot_txt_html = f"\n\n💰 <b>إجمالي الفاتورة الكلي:</b> {tot_val} ج.م" if tot_sum > 0 else ""
    summary = f"📋 <b>فاتورة طلبات الجملة ({len(cart)} أصناف):</b>\n\n" + "\n\n".join(lines) + tot_txt_html
    
    del_btn_text = "❌ حذف صنف آخر" if is_after_delete else "❌ حذف صنف"
    
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
    await send_cart_view(context.bot, update.effective_chat.id, uid, is_after_delete=False)

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

    m_head = await query.message.reply_text("🗑️ <b>اختر الصنف الذي تريد حذفه:</b>", parse_mode=ParseMode.HTML)
    sent_delete_messages[uid].append(m_head.message_id)
    
    for idx, it in enumerate(cart, 1):
        p_price = it.get('price', 0)
        p_total = it.get('total', 0)
        price_line = f"\n💰 الإجمالي: {p_total} ج.م" if p_total > 0 else ""
        cap = f"❌ <b>صنف ({idx}):</b> {html.escape(it['title'])}\n📦 الكمية: {it['label']}{price_line}"
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
    idx = int(query.data.replace("del_", ""))
    
    if uid in sent_delete_messages:
        for mid in sent_delete_messages[uid]:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
            except: pass
        sent_delete_messages[uid] = []
    
    if uid in user_carts and 0 <= idx < len(user_carts[uid]):
        rem = user_carts[uid].pop(idx)
        save_data(CARTS_FILE, user_carts)
        await query.message.reply_text(f"🗑️ تم حذف ({rem['title']}) بنجاح!")
    
    await send_cart_view(context.bot, update.effective_chat.id, uid, is_after_delete=True)

async def send_wa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    cart = user_carts.get(uid, [])
    if not cart:
        await query.message.reply_text("🛒 الفاتورة فارغة بالفعل.")
        return
        
    lines_wa, tot_sum = [], 0
    for i, it in enumerate(cart, 1):
        pi = f" (القطعة: {it['price']}ج)" if it['price'] > 0 else ""
        ti = f" = {it['total']}ج" if it['total'] > 0 else ""
        lines_wa.append(f"{i}. {it['title']}\n📦 الكمية: {it['label']}{pi}{ti}\n🖼️ رابط: {it['link']}")
        tot_sum += it['total']
        
    tot_val = int(tot_sum) if abs(tot_sum - round(tot_sum)) < 0.05 else round(tot_sum, 2)
    tot_txt_wa = f"\n\n💰 إجمالي الفاتورة الكلي: {tot_val} ج.م" if tot_sum > 0 else ""
    wa_msg = f"مرحباً شركة بورسعيد لاستيراد وتصدير الملابس، أود تأكيد طلب الجملة التالي:\n\n" + "\n\n".join(lines_wa) + tot_txt_wa
    encoded_wa = urllib.parse.quote(wa_msg)
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_wa}"
    
    user_carts[uid] = []
    save_data(CARTS_FILE, user_carts)
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📲 اضغط هنا لفتح الواتساب وإرسال الفاتورة الآن", url=wa_link)]])
    await query.message.reply_text(
        "✅ <b>تم تجهيز الفاتورة بنجاح!</b>\n\nاضغط على الزر أدناه لفتح تطبيق الواتساب وإرسال الطلب فوراً:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE=None):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    user_carts[uid] = []
    save_data(CARTS_FILE, user_carts)
    kb_empty = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقناة لتسوق المزيد", url=DEFAULT_CHANNEL_LINK)]])
    await query.message.reply_text("تم تفريغ الفاتورة بنجاح ✅", reply_markup=kb_empty)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(send_wa, pattern="^send_wa$"))
    app.add_handler(CallbackQueryHandler(manage_items, pattern="^manage_items$"))
    app.add_handler(CallbackQueryHandler(delete_single_item, pattern="^del_\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_quantity_selection, pattern="^add_"))
    app.add_handler(CallbackQueryHandler(ask_custom_qty, pattern="^custom_"))
    
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_user_messages))
    print("البوت يعمل الآن بكفاءة...")
    app.run_polling(drop_pending_updates=True)
                                                    

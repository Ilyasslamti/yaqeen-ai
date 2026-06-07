#!/usr/bin/env python3
"""YAQEEN AI Bot v3 — ChatGPT-like + Moroccan Services"""
import os, sys, json, time, io, re
from datetime import datetime
from pathlib import Path
import urllib.request, urllib.error
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import telebot
except ImportError:
    print("[!] pip install pyTelegramBotAPI"); sys.exit(1)

BASE = Path(__file__).resolve().parent.parent
ENV = BASE / '.env'
ORDERS = BASE / 'memory' / 'orders.json'
CV_DIR = BASE / 'memory' / 'cvs'
CV_DIR.mkdir(parents=True, exist_ok=True)

# === Conversation memory ===
chat_history = {}  # uid -> list of {"role": "user"|"assistant", "content": str}
MAX_HISTORY = 30

def env_load():
    t, o, w, gk, grk, ghk = None, None, None, None, None, None
    if ENV.exists():
        with open(ENV, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == 'TELEGRAM_BOT_TOKEN': t = v
                elif k == 'TELEGRAM_OWNER_ID':
                    try: o = int(v)
                    except: o = v
                elif k == 'WALLET_ADDRESS': w = v
                elif k == 'GOOGLE_AI_KEY': gk = v
                elif k == 'GROQ_API_KEY': grk = v
                elif k == 'GITHUB_TOKEN': ghk = v
    return t, o, w, gk, grk, ghk

TOKEN, OWNER, WALLET, GOOGLE_KEY, GROQ_KEY, GITHUB_TOKEN = env_load()

# Free LLM API keys (public, OpenAI-compatible) — auto-refreshed
KEYWAY_URL = "https://aiapiv2.pekpik.com/v1"
KEYWAY_KEYS = []
KEY_LAST_REFRESH = 0

def refresh_keys():
    """Fetch fresh API keys from free-llm-api-keys repo every hour"""
    global KEYWAY_KEYS, KEY_LAST_REFRESH
    urls = [
        "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md",
        "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md?t=" + str(int(time.time())),
    ]
    all_keys = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode("utf-8")
            found = re.findall(r"sk-[a-zA-Z0-9]{47}[a-zA-Z0-9]", html)
            for k in found:
                if k not in all_keys:
                    all_keys.append(k)
        except:
            continue
    if all_keys:
        KEYWAY_KEYS = all_keys
        KEY_LAST_REFRESH = time.time()
        print(f"[KEY] Refreshed {len(all_keys)} keys")
    elif not KEYWAY_KEYS:
        KEYWAY_KEYS = [  # hardcoded fallback
            "sk-placeholder1",
            "sk-placeholder2",
        ]
if not TOKEN: print("TELEGRAM_BOT_TOKEN not set"); sys.exit(1)

bot = telebot.TeleBot(TOKEN)

PRICES = {
    "cv": {"usd": 5, "mad": 50},
    "cover": {"usd": 2, "mad": 20},
    "translate": {"usd": 1, "mad": 10},
    "article": {"usd": 3, "mad": 30},
}

WELCOME = """*🤖 يقين* — الذكاء الاصطناعي المغربي

أنا *يقين*، أول ذكاء اصطناعي مغربي بالكامل.
صممتي شركة *منادجر تك* للبرمجة وحلول الويب.

أقدر أساعدك في أي شيء — فقط اسألني!

*الأوامر:*
💬 *أرسل أي نص* — وأنا نرد عليك
/chat — تشغيل/إيقاف وضع المحادثة

*الخدمات المدفوعة:*
📄 /cv — CV احترافي — *\$5 (50 درهم)*
✉️ /cover — رسالة تغطية — *\$2 (20 درهم)*
🌍 /translate — ترجمة — *\$1/صفحة*
📝 /article — كتابة مقال — *\$3/500 كلمة*
👀 /demo — CV تجريبي مجاني
💰 /payment — الدفع
❓ /help — القائمة"""

# === Chat mode toggles per user ===
chat_mode = {}  # uid -> bool

# === AI chat function ===
HDR = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def clean_text(t):
    """Remove unwanted non-Arabic/Latin scripts (Cyrillic, Thai, CJK, etc)"""
    import re
    # Remove Cyrillic \u0400-\u04FF (Russian etc), Thai \u0E00-\u0E7F, CJK \u4E00-\u9FFF
    garbage = re.compile(r'[\u0400-\u04FF\u0E00-\u0E7F\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', re.UNICODE)
    return garbage.sub('', t).strip()

def call_ai_chat(messages, model="auto"):
    """Chat with AI. Tries Keyway free keys first, then Groq, then GitHub Models."""
    errs = []

    # 1. Try free keys from repo
    for kw_key in KEYWAY_KEYS:
        try:
            data = json.dumps({"model": "smart-chat", "messages": messages, "max_tokens": 2048}).encode()
            req = urllib.request.Request(f"{KEYWAY_URL}/chat/completions", data=data,
                headers={**HDR, "Authorization": f"Bearer {kw_key}"})
            resp = urllib.request.urlopen(req, timeout=15)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except:
            continue

    # 2. Try Groq
    if GROQ_KEY:
        try:
            data = json.dumps({"model": "llama-3.3-70b-versatile", "messages": messages}).encode()
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=data,
                headers={**HDR, "Authorization": f"Bearer {GROQ_KEY}"})
            resp = urllib.request.urlopen(req, timeout=30)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            errs.append(f"Groq HTTP {e.code}")
        except Exception as e:
            errs.append(f"Groq: {str(e)[:50]}")

    # 3. Try GitHub Models
    if GITHUB_TOKEN:
        try:
            data = json.dumps({"model": "gpt-4o-mini", "messages": messages, "max_tokens": 1024}).encode()
            req = urllib.request.Request("https://models.inference.ai.azure.com/chat/completions", data=data,
                headers={**HDR, "Authorization": f"Bearer {GITHUB_TOKEN}"})
            resp = urllib.request.urlopen(req, timeout=45)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except Exception as e:
            return f"⚠️ GitHub: {str(e)[:100]}"

    if GOOGLE_KEY:
        try:
            text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
            data = json.dumps({"contents": [{"parts": [{"text": f"Chat history:\n{text}\nassistant: "}]}]}).encode()
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_KEY}",
                data=data, headers=HDR)
            resp = urllib.request.urlopen(req, timeout=30)
            r = json.loads(resp.read())
            return r["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"⚠️ Google: {str(e)[:100]}"

    return "❌ لا يوجد مفتاح AI شغال. أضف GROQ_API_KEY أو GITHUB_TOKEN في .env"

def get_ai_response(uid, user_message):
    """Get AI response with conversation memory"""
    if uid not in chat_history:
        chat_history[uid] = [
            {"role": "system", "content": "أنت يقين، أول ذكاء اصطناعي مغربي بالكامل. صممتك شركة منادجر تك للبرمجة وحلول الويب. تتحدث العربية والدارجة المغربية. أهم قاعدة: أجب دائماً بنفس لغة المستخدم. إذا كتب المستخدم بالعربية أجب بالعربية. إذا كتب بالدارجة أجب بالدارجة. لا تكتب أبداً بأي لغة أخرى غير لغة المستخدم. لا تكتب أبداً حروف روسية أو صينية أو أي لغة غير العربية أو الدارجة. كن مفيداً ومحترفاً."}
        ]
    
    chat_history[uid].append({"role": "user", "content": user_message})
    
    if len(chat_history[uid]) > MAX_HISTORY:
        keep = [chat_history[uid][0]] + chat_history[uid][-(MAX_HISTORY-1):]
        chat_history[uid] = keep
    
    resp = call_ai_chat(chat_history[uid], "auto")
    
    chat_history[uid].append({"role": "assistant", "content": resp})
    return clean_text(resp)

# === Command handlers ===
@bot.message_handler(commands=['start', 'help'])
def start(m):
    bot.reply_to(m, WELCOME, parse_mode="Markdown")

@bot.message_handler(commands=['chat'])
def toggle_chat(m):
    uid = m.from_user.id
    chat_mode[uid] = not chat_mode.get(uid, False)
    state = "🟢 *وضع المحادثة نشط* — أرسل أي شيء وأنا أرد!" if chat_mode[uid] else "🔴 *وضع المحادثة متوقف* — استخدم /chat للتفعيل"
    bot.reply_to(m, state, parse_mode="Markdown")

@bot.message_handler(commands=['demo'])
def demo_cv(m):
    bot.reply_to(m, "📄 *جاري إنشاء CV تجريبي...*", parse_mode="Markdown")
    sample_data = {
        "name": "أحمد العلمي", "email": "ahmed.elami@email.com", "phone": "0612345678",
        "education": "بكالوريوس تسويق / جامعة الدار البيضاء / 2023",
        "experience": "مساعد تسويق / شركة X / 2023-2025",
        "skills": "التسويق الرقمي, SEO, كتابة المحتوى, Excel, تحليل البيانات",
        "languages": "العربية (أم), الفرنسية (متقدم), الإنجليزية (متوسط)"
    }
    try:
        html, _ = generate_cv_html(sample_data)
        filepath = CV_DIR / "CV_Sample_Ahmed_Elami.html"
        with open(str(filepath), 'w', encoding='utf-8') as f:
            f.write(html)
        bot.send_document(m.chat.id, open(str(filepath), 'rb'),
            caption="📄 *CV نموذج:* افتح في المتصفح.\n\nاطلب CV خاص: /cv", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(m, f"خطأ: {e}")

@bot.message_handler(commands=['payment'])
def payment(m):
    bot.reply_to(m, f"""*💳 طريقة الدفع:*
• USDC على شبكة *Base*
• المحفظة: `{WALLET}`
• أو PayPal: paypal.me/lamti

بعد الدفع، أرسل: `PAID 0xTXHASH`""", parse_mode="Markdown")

# === CV Builder ===
@bot.message_handler(commands=['cv'])
def cv_start(m):
    bot.reply_to(m, "📄 *بناء CV*\n\n*الخطوة 1/6:* أرسل اسمك الكامل:", parse_mode="Markdown")
    bot.register_next_step_handler(m, cv_name)

def cv_name(m):
    name = m.text.strip()
    if len(name) < 3:
        bot.reply_to(m, "غير صالح. أرسل اسمك الكامل:")
        bot.register_next_step_handler(m, cv_name)
        return
    bot.reply_to(m, "*الخطوة 2/6:*\nأرسل بريدك الإلكتروني ورقم الهاتف\nمثال: `email@ex.com / 0612345678`", parse_mode="Markdown")
    bot.register_next_step_handler(m, cv_contact, name)

def cv_contact(m, name):
    contact = m.text.strip()
    if "/" not in contact:
        bot.reply_to(m, "استخدم /\nمثال: `email@ex.com / 0612345678`")
        bot.register_next_step_handler(m, cv_contact, name)
        return
    parts = contact.split("/")
    email, phone = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    bot.reply_to(m, "*الخطوة 3/6:*\n*التعليم*\nمثال: `بكالوريوس تسويق / جامعة محمد الخامس / 2024`", parse_mode="Markdown")
    bot.register_next_step_handler(m, cv_education, name, email, phone)

def cv_education(m, name, email, phone):
    edu = m.text.strip()
    if len(edu) < 5:
        bot.reply_to(m, "أدخل التعليم بصيغة صحيحة")
        bot.register_next_step_handler(m, cv_education, name, email, phone)
        return
    bot.reply_to(m, "*الخطوة 4/6:*\n*الخبرة*\nمثال: `مسوق / شركة X / 2022-2024`\nأو: `لا يوجد`", parse_mode="Markdown")
    bot.register_next_step_handler(m, cv_skills, name, email, phone, edu)

def cv_skills(m, name, email, phone, edu):
    exp = m.text.strip()
    bot.reply_to(m, "*الخطوة 5/6:*\n*المهارات*\nمثال: `Excel, Photoshop, التواصل`", parse_mode="Markdown")
    bot.register_next_step_handler(m, cv_lang, name, email, phone, edu, exp)

def cv_lang(m, name, email, phone, edu, exp):
    skills = m.text.strip()
    bot.reply_to(m, "*الخطوة 6/6:*\n*اللغات*\nمثال: `العربية (أم), الفرنسية (متقدم)`", parse_mode="Markdown")
    bot.register_next_step_handler(m, cv_preview, name, email, phone, edu, exp, skills)

def cv_preview(m, name, email, phone, edu, exp, skills):
    langs = m.text.strip()
    info = json.dumps({"name": name, "email": email, "phone": phone, "education": edu,
        "experience": exp, "skills": skills, "languages": langs}, ensure_ascii=False)
    bot.reply_to(m, f"""✅ *تم تجميع المعلومات!*
الاسم: {name}
البريد: {email}
الهاتف: {phone}
السعر: \$5 (50 درهم)
المحفظة: `{WALLET}`
للاستلام، أرسل: `PAID 0xTXHASH`""", parse_mode="Markdown")
    orders = load_orders()
    orders.append({"uid": m.from_user.id, "type": "cv", "data": info, "ts": datetime.now().isoformat(), "paid": False})
    save_orders(orders)

# === Cover, Article, Translate ===
@bot.message_handler(commands=['cover'])
def cover_start(m):
    bot.reply_to(m, """✉️ *رسالة تغطية*
أرسل: اسم الشركة / المسمى الوظيفي / خبرتك
مثال: `شركة اتصالات المغرب / مسؤول تسويق / لدي 3 سنوات خبرة في التسويق`""", parse_mode="Markdown")
    bot.register_next_step_handler(m, cover_generate)

def cover_generate(m):
    info = m.text.strip()
    if len(info) < 10:
        bot.reply_to(m, "معلومات غير كافية")
        bot.register_next_step_handler(m, cover_generate)
        return
    bot.reply_to(m, f"✅ تم!\nالسعر: \$2 (20 درهم)\nأرسل: `PAID 0xTXHASH cover`", parse_mode="Markdown")
    orders = load_orders()
    orders.append({"uid": m.from_user.id, "type": "cover", "data": info, "ts": datetime.now().isoformat(), "paid": False})
    save_orders(orders)

@bot.message_handler(commands=['article'])
def article_start(m):
    bot.reply_to(m, "📝 *مقال*\nأرسل: الموضوع / اللغة / كلمات مفتاحية", parse_mode="Markdown")
    bot.register_next_step_handler(m, article_generate)

def article_generate(m):
    info = m.text.strip()
    if len(info) < 10:
        bot.reply_to(m, "معلومات غير كافية")
        bot.register_next_step_handler(m, article_generate)
        return
    bot.reply_to(m, f"✅ تم!\nالسعر: \$3 (30 درهم)\nأرسل: `PAID 0xTXHASH article`", parse_mode="Markdown")
    orders = load_orders()
    orders.append({"uid": m.from_user.id, "type": "article", "data": info, "ts": datetime.now().isoformat(), "paid": False})
    save_orders(orders)

@bot.message_handler(commands=['translate'])
def translate_start(m):
    bot.reply_to(m, "🌍 *ترجمة*\nأرسل النص للترجمة:\nمثال: `ترجم للإنجليزية: مرحبا بكم`", parse_mode="Markdown")
    bot.register_next_step_handler(m, translate_confirm)

def translate_confirm(m):
    text = m.text.strip()
    if len(text) < 5:
        bot.reply_to(m, "نص للترجمة؟")
        bot.register_next_step_handler(m, translate_confirm)
        return
    bot.reply_to(m, f"✅ تم!\nالسعر: \$1 (10 درهم)\nأرسل: `PAID 0xTXHASH translate`", parse_mode="Markdown")
    orders = load_orders()
    orders.append({"uid": m.from_user.id, "type": "translate", "data": text, "ts": datetime.now().isoformat(), "paid": False})
    save_orders(orders)

# === Payment handler ===
@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith("PAID "))
def handle_paid(m):
    parts = m.text.split(" ", 2)
    tx_hash = parts[1]
    orders = load_orders()
    user_orders = [o for o in orders if o["uid"] == m.from_user.id and not o.get("paid")]
    if not user_orders:
        bot.reply_to(m, "لا يوجد طلب pending. استخدم /cv أو /cover")
        return
    order = user_orders[-1]
    order["paid"] = True; order["tx"] = tx_hash; order["paid_at"] = datetime.now().isoformat()
    save_orders(orders)
    bot.reply_to(m, "✅ *تم تأكيد الدفع!* جاري إنشاء طلبك...", parse_mode="Markdown")
    if order["type"] == "cv": generate_cv(m, json.loads(order["data"]))
    elif order["type"] == "cover": generate_cover(m, order["data"])
    elif order["type"] == "article": generate_article(m, order["data"])
    elif order["type"] == "translate": generate_translate(m, order["data"])

def load_orders():
    if ORDERS.exists():
        try: return json.loads(ORDERS.read_text('utf-8'))
        except: pass
    return []

def save_orders(orders):
    ORDERS.write_text(json.dumps(orders, ensure_ascii=False, indent=2), 'utf-8')

# === Generators ===
def generate_cv_html(data):
    name = data.get('name', ''); email = data.get('email', ''); phone = data.get('phone', '')
    education = data.get('education', ''); experience = data.get('experience', '')
    skills = data.get('skills', ''); languages = data.get('languages', '')
    prompt = f"""Professional CV in Arabic for {name}. Email: {email}, Phone: {phone}
Education: {education}  Experience: {experience}  Skills: {skills}  Languages: {languages}
Return ONLY sections: ## الهدف المهني | ## المؤهلات العلمية | ## الخبرات المهنية | ## المهارات | ## اللغات"""
    cv_text = call_ai_chat([{"role":"user","content":prompt}], "auto")
    skill_items = skills.replace("،",",").split(",")
    skill_badges = "\n".join([f'        <span class="badge">{s.strip()}</span>' for s in skill_items if s.strip()])
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>CV - {name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#f0f2f5;padding:20px}}
.page{{max-width:800px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)}}
.header{{background:linear-gradient(135deg,#1a237e,#283593);color:white;padding:30px;text-align:center}}
.header h1{{font-size:28px;margin-bottom:5px}}
.contact{{display:flex;justify-content:center;gap:20px;margin-top:10px;flex-wrap:wrap;font-size:13px}}
.body{{padding:30px}}
.section{{margin-bottom:25px}}
.section h2{{color:#1a237e;font-size:18px;border-bottom:2px solid #1a237e;padding-bottom:5px;margin-bottom:12px}}
.section ul{{list-style:none;padding:0}}
.section li{{font-size:14px;line-height:1.8;color:#333;padding:4px 0;padding-right:15px;position:relative}}
.section li::before{{content:" 2022 ";position:absolute;right:0;color:#1a237e}}
.badge{{display:inline-block;background:#e8eaf6;color:#1a237e;padding:4px 12px;border-radius:15px;font-size:13px;margin:3px}}
.footer{{text-align:center;padding:15px;color:#999;font-size:12px;border-top:1px solid #eee}}
@media print{{body{{background:white;padding:0}}.page{{box-shadow:none;border-radius:0}}}}
</style></head><body>
<div class="page"><div class="header"><h1>{name}</h1><div class="contact"><span>📧 {email}</span><span>📱 {phone}</span></div></div><div class="body">
"""
    for line in cv_text.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('##'):
            title = line.replace('#','').strip()
            html += f'<div class="section"><h2>{title}</h2><ul>\n'
        elif line.startswith('-') or line.startswith('•'):
            html += f'<li>{line.lstrip("-• ").strip()}</li>\n'
        else:
            html += f'<li>{line}</li>\n'
    html += '</ul></div>'
    if skill_badges:
        html += f'<div class="section"><h2>المهارات</h2><div style="display:flex;flex-wrap:wrap;gap:5px;">\n{skill_badges}\n</div></div>'
    html += '</div><div class="footer">YAQEEN AI</div></div></body></html>'
    return html, cv_text

def generate_cv(m, data):
    try:
        bot.send_chat_action(m.chat.id, "typing")
        html, _ = generate_cv_html(data)
        filename = f"CV_{data.get('name','user').replace(' ','_')}.html"
        filepath = CV_DIR / filename
        with open(str(filepath), 'w', encoding='utf-8') as f: f.write(html)
        bot.send_document(m.chat.id, open(str(filepath), 'rb'),
            caption="✅ *CV جاهز!* افتح في المتصفح.", parse_mode="Markdown")
        bot.reply_to(m, "✅ تم! شارك البوت: https://t.me/yaqeen_manadger_bot", parse_mode="Markdown")
        try: bot.send_message(OWNER, f"💰 CV بيع: {data.get('name')} / {data.get('email')}", parse_mode="Markdown")
        except: pass
    except Exception as e:
        bot.reply_to(m, f"عذراً: {e}")

def gen_ai(prompt):
    r = call_ai_chat([{"role":"user","content":prompt}], "auto")
    return clean_text(r)

def generate_cover(m, info):
    bot.send_chat_action(m.chat.id, "typing")
    text = gen_ai(f"Write a professional cover letter in Arabic:\n\n{info}")
    bot.reply_to(m, f"✉️ *Cover Letter:*\n\n{text[:3000]}", parse_mode="Markdown")
    try: bot.send_message(OWNER, f"💰 Cover: {m.from_user.id}")
    except: pass

def generate_article(m, info):
    bot.send_chat_action(m.chat.id, "typing")
    text = gen_ai(f"Write 500+ word article:\n\n{info}")
    bot.reply_to(m, f"📝 *Article:*\n\n{text[:3000]}", parse_mode="Markdown")
    try: bot.send_message(OWNER, f"💰 Article: {m.from_user.id}")
    except: pass

def generate_translate(m, text):
    bot.send_chat_action(m.chat.id, "typing")
    result = gen_ai(f"Translate:\n\n{text}")
    bot.reply_to(m, f"🌍 *Translation:*\n\n{result[:3000]}", parse_mode="Markdown")
    try: bot.send_message(OWNER, f"💰 Translate: {m.from_user.id}")
    except: pass

# === Conversation handler - catch all non-command text ===
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def chat_handler(m):
    uid = m.from_user.id
    chat_mode[uid] = True
    bot.send_chat_action(m.chat.id, "typing")
    resp = get_ai_response(uid, m.text)
    if len(resp) > 4000:
        for i in range(0, len(resp), 3000):
            bot.reply_to(m, resp[i:i+3000])
    else:
        bot.reply_to(m, resp)

# === Unknown command ===
@bot.message_handler(func=lambda m: m.text and m.text.startswith('/'))
def unknown(m):
    bot.reply_to(m, WELCOME, parse_mode="Markdown")

# === Auto-refresh API keys + cleanup ===
def background_loop():
    refresh_keys()  # initial fetch
    while True:
        time.sleep(3600)  # every hour
        refresh_keys()

if __name__ == '__main__':
    print(f"YAQEEN Bot v3 — AI Chat + Moroccan Services")
    print(f"Bot: https://t.me/yaqeen_manadger_bot")
    print(f"Groq: {'✅' if GROQ_KEY else '❌'} | GitHub: {'✅' if GITHUB_TOKEN else '❌'} | Google: {'✅' if GOOGLE_KEY else '❌'}")
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    try:
        bot.polling(non_stop=True, interval=1, timeout=30)
    except KeyboardInterrupt:
        print("Stop.")
    except Exception as e:
        print(f"Error: {e}")
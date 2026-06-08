#!/usr/bin/env python3
"""YAQEEN Webhook Bot — للاستضافة على PythonAnywhere (مجاني، لا يحتاج بطاقة)"""
import os, sys, json, time, re, logging, urllib.request
from pathlib import Path
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

try:
    import telebot
    from flask import Flask, request, jsonify
except ImportError:
    print("pip install pyTelegramBotAPI flask"); sys.exit(1)

BASE = Path(__file__).resolve().parent.parent

# === تحميل المفاتيح من المتغيرات ===
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER = int(os.environ.get("TELEGRAM_OWNER_ID", "0"))
WALLET = os.environ.get("WALLET_ADDRESS", "0xD0366D78055b8c637c44d769D1A1371106d13552")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GOOGLE_KEY = os.environ.get("GOOGLE_AI_KEY", "")

if not TOKEN: print("TELEGRAM_BOT_TOKEN required"); sys.exit(1)

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# === ذاكرة المحادثة ===
chat_history = {}
HDR = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def clean_text(t):
    return re.sub(r'[\u0400-\u04FF\u0E00-\u0E7F\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', '', t).strip()

def call_ai(messages):
    """Try Keyway smart-chat keys, then Groq, then GitHub"""
    # Keyway keys from env or use built-in
    keys_env = os.environ.get("KEYWAY_KEYS", "")
    keys = keys_env.split(",") if keys_env else []
    if not keys:
        keys = [
            "sk-placeholder1",
            "sk-placeholder2",
        ]
    for k in keys:
        try:
            d = json.dumps({"model":"smart-chat","messages":messages,"max_tokens":2048}).encode()
            req = urllib.request.Request("https://aiapiv2.pekpik.com/v1/chat/completions", d,
                headers={**HDR, "Authorization": f"Bearer {k.strip()}"})
            resp = urllib.request.urlopen(req, timeout=20)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except: continue
    if GROQ_KEY:
        try:
            d = json.dumps({"model":"llama-3.3-70b-versatile","messages":messages}).encode()
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", d,
                headers={**HDR, "Authorization": f"Bearer {GROQ_KEY}"})
            resp = urllib.request.urlopen(req, timeout=20)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except: pass
    if GITHUB_TOKEN:
        try:
            d = json.dumps({"model":"gpt-4o-mini","messages":messages,"max_tokens":1024}).encode()
            req = urllib.request.Request("https://models.inference.ai.azure.com/chat/completions", d,
                headers={**HDR, "Authorization": f"Bearer {GITHUB_TOKEN}"})
            resp = urllib.request.urlopen(req, timeout=20)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except: pass
    return "⚠️ حدث خطأ، حاول مرة أخرى."

def get_reply(uid, msg):
    if uid not in chat_history:
        chat_history[uid] = [
            {"role":"system","content":"أنت يقين، أول ذكاء اصطناعي مغربي بالكامل. صممتك شركة منادجر تك للبرمجة وحلول الويب. تتحدث العربية والدارجة المغربية. أهم قاعدة: أجب دائماً بنفس لغة المستخدم. إذا كتب المستخدم بالعربية أجب بالعربية. إذا كتب بالدارجة أجب بالدارجة. لا تكتب أبداً بأي لغة أخرى غير لغة المستخدم. لا تكتب أبداً حروف روسية أو صينية أو أي لغة غير العربية أو الدارجة. كن مفيداً ومحترفاً."}
        ]
    chat_history[uid].append({"role":"user","content":msg})
    resp = call_ai(chat_history[uid])
    chat_history[uid].append({"role":"assistant","content":resp})
    return clean_text(resp)

# === API for Github Pages UI ===
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    msg = data.get("message", "")
    uid = request.remote_addr
    reply = get_reply(uid, msg)
    return jsonify({"reply": reply})

# === Webhook route ===
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status":"ok","bot":"YAQEEN"})

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_data().decode("utf-8")
    update = json.loads(update)
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        uid = msg["from"]["id"]
        text = msg.get("text","")
        name = msg["from"].get("first_name","")
        
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd in ["/start","/help"]:
                bot.send_message(chat_id, 
                    "*🤖 يقين* — الذكاء الاصطناعي المغربي\nصممتي شركة *منادجر تك* للبرمجة وحلول الويب.\n\nأرسل أي شيء وأنا نرد عليك!\n\n📄 /cv — CV \$5\n✉️ /cover — رسالة تغطية \$2\n🌍 /translate — ترجمة \$1\n📝 /article — مقال \$3\n👀 /demo — CV تجريبي\n💰 /payment — الدفع", parse_mode="Markdown")
            elif cmd == "/payment":
                bot.send_message(chat_id, f"💳 USDC (Base): `{WALLET}`\nPayPal: paypal.me/lamti", parse_mode="Markdown")
            elif cmd == "/chat":
                bot.send_message(chat_id, "💬 أرسل أي شيء وأنا نرد عليك")
            elif cmd == "/demo":
                bot.send_message(chat_id, "👀 جرب /cv لطلب CV تجريبي")
            else:
                bot.send_message(chat_id, "استخدم /help للقائمة")
        else:
            reply = get_reply(uid, text)
            if len(reply) > 4000:
                for i in range(0, len(reply), 3000):
                    bot.send_message(chat_id, reply[i:i+3000])
            else:
                bot.send_message(chat_id, reply)
    return "OK", 200

# === تشغيل السيرفر ===
if __name__ == "__main__":
    print("=== YAQEEN — Webhook Bot + API ===")
    print()
    print("🔴 للتشغيل على PythonAnywhere (مجاني 24/7):")
    print("  1. سجل في https://www.pythonanywhere.com")
    print("  2. اذهب لـ Web tab ← Add new web app ← Manual Config ← Python 3.11")
    print("  3. ضع هذا الملف في /home/$(whoami)/mysite/")
    print(f"  4. في WSGI file, أضف: from webhook_bot import app as application")
    print("  5. في Web tab ← Environment variables, أضف:")
    print(f"     TELEGRAM_BOT_TOKEN = {TOKEN[:20]}...")
    print("     GROQ_API_KEY = (المفتاح)")
    print("     GITHUB_TOKEN = (اختياري)")
    print("  6. افتح Bash console وشغل:")
    username = os.environ.get("USER", "yourusername")
    print(f"     curl -X POST https://api.telegram.org/bot{TOKEN}/setWebhook -d 'url=https://{username}.pythonanywhere.com/{TOKEN}'")
    print("  7. ارجع لـ Web tab ← Reload")
    print()
    print(f"🚀 بعدها البوت يشتغل 24/7 + API على https://{username}.pythonanywhere.com/api/chat")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

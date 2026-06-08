#!/usr/bin/env python3
"""YAQEEN Webhook Bot — PythonAnywhere + Moroccan RAG"""
import os, sys, json, time, re, urllib.request
from pathlib import Path
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

from flask import Flask, request, jsonify
from morocco_knowledge import MoroccoRAG

BASE = Path(__file__).resolve().parent.parent
RAG = MoroccoRAG()

# === تحميل المفاتيح من المتغيرات ===
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER = int(os.environ.get("TELEGRAM_OWNER_ID", "0"))
WALLET = os.environ.get("WALLET_ADDRESS", "0xD0366D78055b8c637c44d769D1A1371106d13552")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GOOGLE_KEY = os.environ.get("GOOGLE_AI_KEY", "")

if not TOKEN: print("TELEGRAM_BOT_TOKEN required"); sys.exit(1)

app = Flask(__name__)

# === ذاكرة المحادثة ===
chat_history = {}
HDR = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def clean_text(t):
    return re.sub(r'[\u0400-\u04FF\u0E00-\u0E7F\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', '', t).strip()

def tg_send(chat_id, text, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": parse_mode}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data, HDR), timeout=15)
    except: pass

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

SYSTEM_PROMPT = """أنت يقين، أول ذكاء اصطناعي مغربي بالكامل. صممتك شركة منادجر تك للبرمجة وحلول الويب.

أنت خبير شامل في كل ما يخص المغرب:
- التاريخ: الأدارسة، المرابطون، الموحدون، العلويون، الاستعمار، الاستقلال، المسيرة الخضراء
- الجغرافيا: جميع المدن المغربية والجهات والمناطق
- الثقافة: الكسكس، الطاجين، البسطيلة، الحريرة، الشاي، اللباس، الموسيقى (العيطة، كناوة، الراي)، الأمازيغ
- الاقتصاد: الفوسفاط، السياحة، الفلاحة، الصناعة، المبادرة الوطنية للتنمية البشرية
- السياسة: الملك محمد السادس، الدستور، البرلمان، الحكومة
- الرياضة: المنتخب، الوداد، الرجاء، الجيش الملكي
- القانون: مدونة الأسرة، قانون الشغل، الجنسية
- التكنولوجيا: الشركات الناشئة، التحول الرقمي

قواعد صارمة:
1. أجب دائماً بنفس لغة المستخدم (عربية فصحى، دارجة مغربية، أمازيغية)
2. استخدم المعرفة المغربية المقدمة لك في ردودك
3. كن دقيقاً في المعلومات التاريخية والجغرافية
4. لا تكتب أبداً حروفاً من لغات غير العربية (لا روسية، لا صينية، لا تايلاندية)
5. كن مفيداً ومحترفاً وتعكس القيم المغربية الأصيلة
6. إذا سألك المستخدم عن شيء معرفتك فيه محدودة، اعترف بذلك بدلاً من التخمين"""

def get_reply(uid, msg):
    rag_context = RAG.inject(msg)
    if uid not in chat_history:
        system_content = SYSTEM_PROMPT
        if rag_context:
            system_content += rag_context
        chat_history[uid] = [{"role":"system","content": system_content}]
    else:
        if rag_context:
            chat_history[uid].append({"role":"system","content": rag_context})
    chat_history[uid].append({"role":"user","content":msg})
    resp = call_ai(chat_history[uid])
    chat_history[uid].append({"role":"assistant","content":resp})
    history = chat_history[uid]
    chat_history[uid] = [history[0]] + history[-6:] if len(history) > 7 else history
    return clean_text(resp)

# === API for Github Pages UI ===
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})
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
                tg_send(chat_id, 
                    "*\U0001f916 \u064a\u0642\u064a\u0646* — \u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a \u0627\u0644\u0645\u063a\u0631\u0628\u064a\n\u0635\u0645\u0645\u062a\u064a \u0634\u0631\u0643\u0629 *\u0645\u0646\u0627\u062f\u062c\u0631 \u062a\u0643* \u0644\u0644\u0628\u0631\u0645\u062c\u0629 \u0648\u062d\u0644\u0648\u0644 \u0627\u0644\u0648\u064a\u0628.\n\n\u0623\u0631\u0633\u0644 \u0623\u064a \u0634\u064a\u0621 \u0648\u0623\u0646\u0627 \u0646\u0631\u062f \u0639\u0644\u064a\u0643!\n\n\U0001f4c4 /cv \u2014 CV $5\n\u2709\ufe0f /cover \u2014 \u0631\u0633\u0627\u0644\u0629 \u062a\u063a\u0637\u064a\u0629 $2\n\U0001f30d /translate \u2014 \u062a\u0631\u062c\u0645\u0629 $1\n\U0001f4dd /article \u2014 \u0645\u0642\u0627\u0644 $3\n\U0001f440 /demo \u2014 CV \u062a\u062c\u0631\u064a\u0628\u064a\n\U0001f4b0 /payment \u2014 \u0627\u0644\u062f\u0641\u0639", parse_mode="Markdown")
            elif cmd == "/payment":
                tg_send(chat_id, f"\U0001f4b3 USDC (Base): `{WALLET}`\nPayPal: paypal.me/lamti", parse_mode="Markdown")
            elif cmd == "/chat":
                tg_send(chat_id, "\U0001f4ac \u0623\u0631\u0633\u0644 \u0623\u064a \u0634\u064a\u0621 \u0648\u0623\u0646\u0627 \u0646\u0631\u062f \u0639\u0644\u064a\u0643")
            elif cmd == "/demo":
                tg_send(chat_id, "\U0001f440 \u062c\u0631\u0628 /cv \u0644\u0637\u0644\u0628 CV \u062a\u062c\u0631\u064a\u0628\u064a")
            else:
                tg_send(chat_id, "\u0627\u0633\u062a\u062e\u062f\u0645 /help \u0644\u0644\u0642\u0627\u0626\u0645\u0629")
        else:
            reply = get_reply(uid, text)
            if len(reply) > 4000:
                for i in range(0, len(reply), 3000):
                    tg_send(chat_id, reply[i:i+3000])
            else:
                tg_send(chat_id, reply)
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

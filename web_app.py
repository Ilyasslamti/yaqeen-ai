#!/usr/bin/env python3
"""YAQEEN Web App — واجهة ويب أحسن من ChatGPT"""
import os, sys, json, re, urllib.request
from pathlib import Path
from flask import Flask, request, render_template, jsonify

BASE = Path(__file__).resolve().parent
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

app = Flask(__name__)
HDR = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
chat_history = {}

def clean_text(t):
    return re.sub(r'[\u0400-\u04FF\u0E00-\u0E7F\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', '', t).strip()

def call_ai(messages):
    if GROQ_KEY:
        try:
            d = json.dumps({"model": "llama-3.3-70b-versatile", "messages": messages}).encode()
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", d,
                headers={**HDR, "Authorization": f"Bearer {GROQ_KEY}"})
            resp = urllib.request.urlopen(req, timeout=30)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except: pass
    if GITHUB_TOKEN:
        try:
            d = json.dumps({"model": "gpt-4o-mini", "messages": messages, "max_tokens": 1024}).encode()
            req = urllib.request.Request("https://models.inference.ai.azure.com/chat/completions", d,
                headers={**HDR, "Authorization": f"Bearer {GITHUB_TOKEN}"})
            resp = urllib.request.urlopen(req, timeout=30)
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"]
        except: pass
    return "⚠️ حدث خطأ. حاول مرة أخرى."

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    msg = data.get('message', '')
    uid = request.remote_addr
    
    if uid not in chat_history:
        chat_history[uid] = [
            {"role": "system", "content": "أنت يقين، أول ذكاء اصطناعي مغربي بالكامل. صممتك شركة منادجر تك للبرمجة وحلول الويب. تتحدث العربية والدارجة المغربية. أجب دائماً بنفس لغة المستخدم. كن مفيداً ومحترفاً."}
        ]
    chat_history[uid].append({"role": "user", "content": msg})
    reply = call_ai(chat_history[uid])
    chat_history[uid].append({"role": "assistant", "content": reply})
    return jsonify({"reply": clean_text(reply)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🤖 YAQEEN Web App on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

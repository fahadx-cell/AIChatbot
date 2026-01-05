import os
import time
import requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv

# Load .env locally. On Railway, environment variables are set in the dashboard
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Telegram and Gemini URLs
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent?key=" + GEMINI_API_KEY
)

app = FastAPI()

# Simple in-memory rate limiter per user
user_last_message = {}

def rate_limited(user_id, cooldown=5):
    """Returns True if user is sending messages too fast"""
    now = time.time()
    last = user_last_message.get(user_id, 0)
    if now - last < cooldown:
        return True
    user_last_message[user_id] = now
    return False

def send_message(chat_id, text):
    """Send message back to Telegram"""
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def ask_gemini(prompt):
    """Send prompt to Gemini Gemma 3 12B"""
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    r = requests.post(GEMINI_URL, json=payload, timeout=20)
    r.raise_for_status()
    # Return first candidate response
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint"""
    data = await request.json()

    # Ignore non-message updates
    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    if not text:
        return {"ok": True}

    # Rate limit per user
    if rate_limited(user_id):
        send_message(chat_id, "⚠️ Slow down! Demo limit: 1 message every 5 seconds.")
        return {"ok": True}

    # Ask Gemini and send response
    try:
        reply = ask_gemini(text[:1000])  # limit input tokens
        send_message(chat_id, reply[:4000])  # limit Telegram message size
    except Exception:
        send_message(chat_id, "❌ AI is busy. Try again later.")

    return {"ok": True}


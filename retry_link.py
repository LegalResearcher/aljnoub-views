import os
import re
import sys
import time

import requests

API_URL = "https://prince.services/api/v2"
SERVICE_ID = "9336"
QUANTITY = "100"
LINK_PATTERN = re.compile(r"^https://t\.me/aljnoubvoice/\d+$")
DONE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "done_links.txt")


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def mark_done(link):
    os.makedirs(os.path.dirname(DONE_PATH), exist_ok=True)
    existing = []
    if os.path.exists(DONE_PATH):
        with open(DONE_PATH, "r", encoding="utf-8") as file:
            existing = [line.strip() for line in file if line.strip()]
    if link not in existing:
        with open(DONE_PATH, "a", encoding="utf-8") as file:
            file.write(link + "\n")


def main():
    api_key = os.environ.get("API_KEY", "").strip()
    link = os.environ.get("TARGET_LINK", "").strip()
    if not api_key:
        log("❌ المتغير API_KEY غير موجود. أضفه في Settings > Secrets and variables > Actions.")
        return 1
    if not LINK_PATTERN.fullmatch(link):
        log("❌ الرابط غير صالح؛ يلزم رابط منشور من قناة aljnoubvoice.")
        return 2

    log(f"🚀 إعادة تشغيل يدوية للرابط المحدد: {link}")
    log("معالجة: " + link)
    payload = {
        "key": api_key,
        "action": "add",
        "service": SERVICE_ID,
        "link": link,
        "quantity": QUANTITY,
    }
    try:
        response = requests.post(API_URL, data=payload, timeout=30)
    except requests.RequestException as error:
        log(f"⚠️ خطأ اتصال: {type(error).__name__}")
        return 1

    if response.status_code == 401:
        log("❌ المفتاح مرفوض (401).")
        return 1
    if response.status_code != 200:
        log(f"❌ كود الحالة: {response.status_code}")
        return 1
    try:
        result = response.json()
    except ValueError:
        log("⚠️ رد غير متوقع من السيرفر (ليس JSON).")
        return 1

    if "order" in result:
        log(f"✅ تم الطلب. رقم المعاملة: {result['order']}")
        mark_done(link)
        return 0

    message = str(result.get("error", "")).lower()
    if "key" in message:
        log("❌ المفتاح مرفوض (401).")
    elif "balance" in message:
        log("❌ خطأ رصيد.")
    else:
        log("⚠️ لم يقبل مزود الخدمة الطلب؛ راجع حالة الطلب من لوحة الخدمة.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

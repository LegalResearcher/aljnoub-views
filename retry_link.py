import os
import re
import sys

from browser_sender import BrowserSender
from state_store import (
    MAX_SUCCESSFUL_ORDERS_PER_LINK,
    load_success_counts,
    record_success,
)

LINK_PATTERN = re.compile(r"^https://t\.me/aljnoubvoice/\d+$")
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
DONE_PATH = os.path.join(STATE_DIR, "done_links.txt")
SUCCESS_COUNTS_PATH = os.path.join(STATE_DIR, "success_counts.json")


def log(message):
    print(message, flush=True)


def main():
    username = os.environ.get("SITE_USERNAME", "").strip()
    password = os.environ.get("SITE_PASSWORD", "")
    link = os.environ.get("TARGET_LINK", "").strip()
    if not (username and password):
        log("❌ أضف SITE_USERNAME وSITE_PASSWORD في Secrets and variables > Actions.")
        return 1
    if not LINK_PATTERN.fullmatch(link):
        log("❌ الرابط غير صالح؛ يلزم رابط منشور من قناة aljnoubvoice.")
        return 2

    success_counts = load_success_counts(SUCCESS_COUNTS_PATH, DONE_PATH)
    current_count = success_counts.get(link, 0)
    if current_count >= MAX_SUCCESSFUL_ORDERS_PER_LINK:
        log(f"⏹️ وصل الرابط إلى الحد الأقصى: {current_count}/{MAX_SUCCESSFUL_ORDERS_PER_LINK} طلبات ناجحة.")
        return 3

    log(f"🚀 إعادة تشغيل يدوية للرابط المحدد: {link}")
    with BrowserSender(username, password) as sender:
        status = sender(link)

    if status == "ok":
        count = record_success(link, SUCCESS_COUNTS_PATH, DONE_PATH)
        log(f"✅ تم الطلب بنجاح؛ العداد {count}/{MAX_SUCCESSFUL_ORDERS_PER_LINK}.")
        return 0
    log("⚠️ لم ينجح الطلب عبر الموقع.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

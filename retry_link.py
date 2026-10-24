import os
import re
import sys

from browser_sender import BrowserSender
from state_store import (
    MAX_SUCCESSFUL_ORDERS_PER_LINK,
    load_success_counts,
    record_success,
    select_rotating_account,
)

LINK_PATTERN = re.compile(r"^https://t\.me/aljnoubvoice/\d+$")
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
DONE_PATH = os.path.join(STATE_DIR, "done_links.txt")
SUCCESS_COUNTS_PATH = os.path.join(STATE_DIR, "success_counts.json")


def log(message):
    print(message, flush=True)


def main():
    link = os.environ.get("TARGET_LINK", "").strip()
    if not LINK_PATTERN.fullmatch(link):
        log("❌ الرابط غير صالح؛ يلزم رابط منشور من قناة aljnoubvoice.")
        return 2

    success_counts = load_success_counts(SUCCESS_COUNTS_PATH, DONE_PATH)
    current_count = success_counts.get(link, 0)
    if current_count >= MAX_SUCCESSFUL_ORDERS_PER_LINK:
        log(f"⏹️ وصل الرابط إلى الحد الأقصى: {current_count}/{MAX_SUCCESSFUL_ORDERS_PER_LINK} طلبات ناجحة.")
        return 3

    try:
        account_number, username, password = select_rotating_account(os.environ, STATE_DIR)
    except (OSError, ValueError) as error:
        log(f"❌ تعذر اختيار حساب؛ تحقق من الأسرار الثلاثة وحالة account_rotation.json: {error}")
        return 1

    log(f"🚀 إعادة تشغيل يدوية للرابط المحدد: {link} | الحساب رقم {account_number}")
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

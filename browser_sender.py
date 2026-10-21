import os
import re

from playwright.sync_api import sync_playwright

SITE_URL = os.environ.get("SITE_URL", "https://prince.services")
CATEGORY_TEXT = "خدمات مجانية"
SERVICE_TEXT = "9336"
QUANTITY = "100"
CONFIRM_TEXT = "تاكيد الطلب"
SUCCESS_TEXT = "تم استلام طلبك بنجاح"


SELECT_JS = """
(needle) => {
  for (const s of Array.from(document.querySelectorAll('select'))) {
    if (!(s.offsetWidth || s.offsetHeight || s.getClientRects().length)) continue;
    for (const o of s.options) {
      if (o.text.includes(needle)) {
        s.value = o.value;
        s.dispatchEvent(new Event('input', {bubbles: true}));
        s.dispatchEvent(new Event('change', {bubbles: true}));
        if (window.jQuery) { window.jQuery(s).trigger('change'); }
        return o.text.trim();
      }
    }
  }
  return null;
}
"""


class BrowserSender:
    """تسجيل الدخول مرة واحدة وإرسال رابط واحد عبر نموذج الموقع."""

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.pw = None
        self.browser = None
        self.page = None
        self.logged_in = False

    def __enter__(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            headless=True, args=["--no-sandbox"]
        )
        context = self.browser.new_context(
            locale="ar", viewport={"width": 1280, "height": 1800}
        )
        context.set_default_timeout(30000)
        self.page = context.new_page()
        return self

    def __exit__(self, *exc):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.pw:
                self.pw.stop()

    def _first_visible(self, *locators):
        for locator in locators:
            try:
                if locator.count() and locator.first.is_visible():
                    return locator.first
            except Exception:
                continue
        return None

    def _link_field(self):
        p = self.page
        return self._first_visible(
            p.locator("#orders-link"),
            p.get_by_label("الرابط", exact=True),
            p.locator("input[name*='link' i]"),
            p.locator("input[placeholder*='رابط']"),
        )

    def _quantity_field(self):
        p = self.page
        return self._first_visible(
            p.locator("#orders-quantity"),
            p.get_by_label("الكمية", exact=True),
            p.locator("input[name*='quantity' i]"),
        )

    def _login(self):
        p = self.page
        p.goto(SITE_URL + "/", wait_until="commit")
        p.wait_for_timeout(1000)
        password_field = p.locator("input[type='password']").first
        try:
            password_field.wait_for(state="visible", timeout=20000)
        except Exception:
            return self._link_field() is not None

        form = password_field.locator("xpath=ancestor::form[1]")
        user_field = form.locator(
            "input[type='text'], input[type='email'], input:not([type])"
        ).first
        user_field.fill(self.username)
        password_field.fill(self.password)
        submit = self._first_visible(
            form.locator("button[type='submit'], input[type='submit']"),
            form.get_by_role("button", name="تسجيل الدخول"),
        )
        if submit is None:
            raise RuntimeError("زر تسجيل الدخول غير موجود")
        submit.click()
        p.wait_for_timeout(1000)
        return not (
            p.locator("input[type='password']").count()
            and p.locator("input[type='password']").first.is_visible()
        )

    def _open_order_page(self):
        p = self.page
        if self._link_field() or p.locator("select#orderform-category").count():
            return True
        for path in ("/neworder", "/new-order", "/"):
            p.goto(SITE_URL + path, wait_until="commit")
            p.wait_for_timeout(1000)
            if self._link_field() or p.locator("select#orderform-category").count():
                return True
        button = p.get_by_text("طلب جديد", exact=True)
        if button.count():
            button.first.evaluate("(element) => element.click()")
            p.wait_for_timeout(500)
        return (
            self._link_field() is not None
            or p.locator("select#orderform-category").count() > 0
        )

    def _select(self, needle, retries=10):
        for _ in range(retries):
            chosen = self.page.evaluate(SELECT_JS, needle)
            if chosen:
                return chosen
            self.page.wait_for_timeout(500)
        return None

    def __call__(self, link):
        p = self.page
        try:
            if not self.logged_in:
                if not self._login():
                    return "fatal"
                self.logged_in = True

            if not self._open_order_page():
                return "fail"
            if not self._select(CATEGORY_TEXT):
                return "fail"
            p.wait_for_timeout(800)
            if not self._select(SERVICE_TEXT):
                return "fail"

            link_field = quantity_field = None
            for _ in range(20):
                link_field = self._link_field()
                quantity_field = self._quantity_field()
                if link_field is not None and quantity_field is not None:
                    break
                p.wait_for_timeout(500)
            if link_field is None or quantity_field is None:
                return "fail"
            link_field.fill(link)
            quantity_field.fill(QUANTITY)

            confirm = self._first_visible(
                p.get_by_role("button", name=CONFIRM_TEXT),
                p.locator(f"button:has-text('{CONFIRM_TEXT}')"),
                p.locator(f"input[type='submit'][value*='{CONFIRM_TEXT}']"),
            )
            if confirm is None:
                return "fail"

            # الزر مثبت أسفل الصفحة وقد تتداخل معه عناصر عائمة؛ النقر البرمجي يتجاوز التداخل.
            confirm.evaluate("(element) => element.click()")
            try:
                p.wait_for_function(
                    "(text) => document.body.innerText.includes(text)",
                    arg=SUCCESS_TEXT,
                    timeout=30000,
                )
            except Exception:
                return "fail"

            p.goto(SITE_URL + "/", wait_until="domcontentloaded")
            return "ok"
        except Exception:
            return "fail"

# Aljnoub Views

يسحب منشورات قناة `@aljnoubvoice` ويرسل طلب مشاهدات لرابط واحد من الطابور في كل تشغيل.
التشغيل كل 25 دقيقة عبر Supabase `pg_cron`، الذي يرسل `workflow_dispatch` إلى GitHub Actions.

## الإعداد
1. أضف المفتاح: Settings > Secrets and variables > Actions > New repository secret
   - الاسم: `API_KEY`
   - القيمة: مفتاح الـ API
2. في Supabase Vault أضف سر GitHub باسم `github_actions_token`، ويجب أن يملك صلاحية تشغيل Actions للمستودع.
3. تشغيل يدوي: تبويب Actions > Aljnoub Views > Run workflow.

## كيف يعمل
- أول تشغيل: يأخذ أحدث منشور فقط.
- بعدها: كل منشور جديد يدخل الطابور بالترتيب، ويُنفَّذ الأقدم أولاً.
- الرابط الذي يفشل 3 مرات يُتخطى.
- خطأ في المفتاح أو الرصيد يوقف التشغيل ويظهر فاشلاً في Actions.

## تصفير الحالة
احذف الملفات داخل مجلد `state/` (ما عدا `.gitkeep`) لبدء من الصفر.

## ملاحظة
المفتاح لا يُكتب في أي ملف. المستودع عام، فملفات `state/` مرئية للجميع.

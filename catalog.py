# ==========================================================
#  DARK ELGENERAL — Project catalog (types, templates, guides)
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

from collections import OrderedDict

import config

PROJECT_TYPES = OrderedDict()

PROJECT_TYPES["website"] = {
    "emoji": "🌐",
    "title": "موقع ويب",
    "desc": "مواقع متجاوبة بتصميم عصري وأنيميشنز سلسة",
    "stack": "HTML • CSS • JavaScript",
    "hosting": "web",
    "templates": [
        ("💼 معرض أعمال",
         "موقع Portfolio شخصي لمطور/مصمم: قسم تعريف، المهارات، معرض أعمال بفلاتر، "
         "آراء العملاء، ونموذج تواصل."),
        ("🍽 موقع مطعم",
         "موقع مطعم فاخر: قائمة طعام مصنفة بصور، حجز طاولة، معرض صور، "
         "مواعيد العمل وخريطة الموقع."),
        ("🛒 متجر إلكتروني",
         "واجهة متجر إلكتروني: عرض منتجات مع بحث وفلاتر، سلة مشتريات تعمل بالـJavaScript، "
         "صفحة تفاصيل المنتج وإتمام الطلب."),
        ("🚀 صفحة هبوط",
         "Landing page لمنتج/تطبيق: Hero جذاب، المميزات، الأسعار، آراء العملاء، "
         "الأسئلة الشائعة وزر دعوة لاتخاذ إجراء."),
    ],
}

PROJECT_TYPES["telegram_bot"] = {
    "emoji": "🤖",
    "title": "بوت تيليجرام",
    "desc": "بوتات احترافية بأزرار وقواعد بيانات ولوحة أدمن",
    "stack": "Python • pyTelegramBotAPI • SQLite",
    "hosting": "bot",
    "templates": [
        ("🛍 بوت متجر",
         "بوت متجر: أقسام ومنتجات بأزرار، سلة مشتريات، إتمام الطلب مع إشعار للأدمن، "
         "ولوحة أدمن لإضافة وحذف المنتجات."),
        ("🎫 بوت دعم فني",
         "بوت دعم فني: المستخدم يفتح تذكرة، الأدمن يرد من داخل البوت، حالة التذكرة وسجل المحادثات."),
        ("🧠 بوت مسابقات",
         "بوت أسئلة ومسابقات: أسئلة بأزرار، نقاط ولوحة صدارة، مستويات صعوبة وإحصائيات."),
        ("📢 اشتراك إجباري وإذاعة",
         "بوت اشتراك إجباري: التحقق من الاشتراك في القنوات، إحصائيات، "
         "وإرسال رسائل جماعية من الأدمن."),
    ],
}

PROJECT_TYPES["discord_bot"] = {
    "emoji": "💬",
    "title": "بوت ديسكورد",
    "desc": "بوتات سيرفرات ديسكورد بأوامر Slash وأزرار",
    "stack": "Python • discord.py",
    "hosting": "bot",
    "templates": [
        ("🛡 بوت إدارة",
         "بوت إدارة للسيرفر: kick / ban / mute / clear بأوامر Slash، نظام تحذيرات، سجل إجراءات."),
        ("🎮 ألعاب وترفيه",
         "بوت ألعاب بسيطة مع نظام عملات ومستويات XP ولوحة صدارة."),
        ("🎫 نظام تذاكر",
         "نظام تذاكر دعم بالأزرار: قناة خاصة لكل تذكرة، إغلاق التذكرة وحفظ سجل المحادثة."),
        ("👋 ترحيب ورتب",
         "ترحيب تلقائي برسائل مزخرفة (Embeds) ورتب تلقائية عند التفاعل مع رسالة."),
    ],
}

PROJECT_TYPES["python_tool"] = {
    "emoji": "🐍",
    "title": "أداة Python",
    "desc": "ملف Python واحد جاهز للتشغيل (.py)",
    "stack": "Python 3 • ملف واحد",
    "hosting": "bot",
    "templates": [
        ("🔍 فاحص روابط",
         "أداة سطر أوامر تفحص قائمة روابط وتعرض حالة كل رابط وسرعة الاستجابة وتحفظ تقريرًا بصيغة CSV."),
        ("📁 منظّم ملفات",
         "سكريبت ينظّم مجلدًا تلقائيًا حسب نوع الملفات مع وضع معاينة (dry-run) وسجل للعمليات."),
        ("📊 مُحلّل بيانات",
         "أداة تقرأ ملفات CSV وتطبع إحصائيات وتنتج تقريرًا منسقًا وملخصًا قابلًا للحفظ."),
        ("⏰ أتمتة مهام",
         "جدولة مهام متكررة بملف إعدادات مع تسجيل (logging) وإشعار عند الانتهاء."),
    ],
}


def is_single_file(key):
    """Types delivered as one file instead of a ZIP."""
    return key == "python_tool"


def type_info(key):
    return PROJECT_TYPES.get(key) or {
        "emoji": "📦", "title": key, "desc": "", "stack": "", "hosting": "bot", "templates": [],
    }


def type_label(key):
    info = type_info(key)
    return f"{info['emoji']} {info['title']}"


def hosting_url(key):
    return config.WEB_HOSTING_URL if type_info(key)["hosting"] == "web" else config.BOT_HOSTING_URL


def hosting_label(key):
    if type_info(key)["hosting"] == "web":
        return "🌐 انشر على Vercel"
    return "🤖 استضف البوت"


# ----------------------------------------------------------
#  Files injected into every ZIP
# ----------------------------------------------------------

def hosting_guide_markdown(key, project_name):
    if type_info(key)["hosting"] == "web":
        return f"""# دليل نشر الموقع — {project_name}

## الطريقة 1: Vercel (مجانًا)
1. أنشئ حسابًا على {config.WEB_HOSTING_URL}
2. ارفع مجلد المشروع إلى GitHub (أو استخدم Vercel CLI).
3. من لوحة Vercel اختر **Add New → Project** ثم اختر المستودع.
4. اترك الإعدادات الافتراضية (Framework Preset: Other) واضغط **Deploy**.
5. بعد ثوانٍ يصبح موقعك متاحًا على رابط `.vercel.app`.

## بالـ CLI
```bash
npm i -g vercel
cd {project_name}
vercel --prod
```

## ملاحظات
- تأكد أن ملف `index.html` موجود في جذر المشروع.
- لربط دومين خاص: Settings → Domains داخل مشروعك على Vercel.

---
{config.COPYRIGHT}
"""
    return f"""# دليل تشغيل المشروع — {project_name}

## استضافة البوتات
1. افتح بوت الاستضافة: {config.BOT_HOSTING_URL}
2. ارفع ملفات المشروع (الملف الرئيسي + الملفات المساعدة).
3. ضع التوكن/المفاتيح داخل ملف الإعدادات قبل الرفع.
4. شغّل البوت من لوحة التحكم داخل بوت الاستضافة.

## التشغيل محليًا
```bash
pip install -r requirements.txt
python main.py
```

## ملاحظات
- احتفظ بالتوكن سرّيًا ولا ترفعه على مستودع عام.
- راجع ملف README.md للتفاصيل الخاصة بمشروعك.

---
{config.COPYRIGHT}
"""


def credit_text(key, project_name):
    return (
        f"Project : {project_name}\n"
        f"Type    : {type_info(key)['title']}\n"
        f"Made by : {config.BOT_NAME} (AI Project Generator)\n"
        f"Developer: {config.DEVELOPER_NAME}\n"
        f"Telegram: https://t.me/{config.CONTACT_TELEGRAM}\n"
        f"\n{config.COPYRIGHT}\n"
    )


def credit_header():
    return (
        "# ----------------------------------------------------------\n"
        f"#  Generated by {config.BOT_NAME} - AI Project Generator\n"
        f"#  Developer: {config.DEVELOPER_NAME} | https://t.me/{config.CONTACT_TELEGRAM}\n"
        f"#  {config.COPYRIGHT}\n"
        "# ----------------------------------------------------------\n"
    )

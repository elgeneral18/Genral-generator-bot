# ==========================================================
#  DARK ELGENERAL — UI: texts, keyboards, animations
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import math
import threading
import time
from urllib.parse import quote

from telebot import types

import catalog
import config
from utils import bar, esc, human_size, log, pretty_date, short

LINE = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
FOOTER = f"<i>{esc(config.COPYRIGHT)}</i>"

WHATSAPP_URL = (
    f"https://wa.me/{config.CONTACT_WHATSAPP}?text="
    + quote("مرحبًا Dark Elgeneral، عندي استفسار بخصوص خدماتك 👋")
)
TELEGRAM_URL = f"https://t.me/{config.CONTACT_TELEGRAM}"

THEME_LABELS = {"dark": "🌙 داكن", "light": "☀️ فاتح", "glass": "🪟 زجاجي"}
LANG_LABELS = {"ar": "🇪🇬 عربي", "en": "🇬🇧 English"}


def card(title, body, footer=True):
    text = f"{title}\n{LINE}\n{body}"
    if footer:
        text += f"\n{LINE}\n{FOOTER}"
    return text


# ----------------------------------------------------------
#  KEYBOARD HELPERS
# ----------------------------------------------------------

def _kb(*rows):
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        markup.row(*row)
    return markup


def _btn(text, data=None, url=None):
    if url:
        return types.InlineKeyboardButton(text, url=url)
    return types.InlineKeyboardButton(text, callback_data=data)


def back_home_row():
    return [_btn("🏠 القائمة الرئيسية", "nav:main")]


def contact_row():
    return [_btn("💬 WhatsApp", url=WHATSAPP_URL), _btn("✈️ Telegram", url=TELEGRAM_URL)]


# ----------------------------------------------------------
#  MAIN MENU
# ----------------------------------------------------------

def welcome_text(name):
    body = (
        f"أهلاً <b>{esc(name)}</b> 👋\n"
        "حوّل فكرتك إلى مشروع كامل جاهز للرفع بالذكاء الاصطناعي:\n\n"
        "🌐 مواقع ويب احترافية\n"
        "🤖 بوتات تيليجرام وديسكورد\n"
        "🐍 أدوات وسكريبتات Python\n"
        "📦 تسليم فوري كملف ZIP + دليل استضافة (وملف .py للأدوات)\n\n"
        "👇 <b>اختر من القائمة</b>"
    )
    return card(f"🌑 <b>{config.BOT_NAME.upper()}</b> 🌑\n<i>مصنع المشاريع بالذكاء الاصطناعي</i>", body)


def main_menu():
    return _kb(
        [_btn("🚀 إنشاء مشروع جديد", "nav:new")],
        [_btn("📂 مشاريعي", "my:0"), _btn("📊 حسابي", "nav:account")],
        [_btn("🖥 الاستضافة", "nav:host"), _btn("💎 المميزات", "nav:features")],
        [_btn("👨‍💻 المطور", "nav:dev"), _btn("⚙️ الإعدادات", "nav:settings")],
        [_btn("📖 المساعدة", "nav:help")],
    )


# ----------------------------------------------------------
#  NEW PROJECT FLOW
# ----------------------------------------------------------

def type_chooser_text():
    lines = []
    for info in catalog.PROJECT_TYPES.values():
        lines.append(f"{info['emoji']} <b>{info['title']}</b>\n   ↳ {info['desc']}\n   <code>{info['stack']}</code>")
    return card("🚀 <b>إنشاء مشروع جديد</b>", "اختر نوع المشروع:\n\n" + "\n\n".join(lines))


def type_chooser_keyboard():
    items = list(catalog.PROJECT_TYPES.items())
    rows = []
    for index in range(0, len(items), 2):
        rows.append([_btn(f"{info['emoji']} {info['title']}", f"type:{key}") for key, info in items[index:index + 2]])
    rows.append(back_home_row())
    return _kb(*rows)


def idea_text(ptype):
    info = catalog.type_info(ptype)
    body = (
        f"{info['emoji']} النوع: <b>{info['title']}</b>\n\n"
        "✍️ <b>اكتب فكرة مشروعك بالتفصيل</b>\n"
        "كلما كانت الفكرة أوضح، كانت النتيجة أدق.\n\n"
        "💡 اذكر: الهدف • الأقسام/الأوامر • الألوان أو الستايل • أي ميزة خاصة.\n\n"
        "⚡ أو اختر <b>قالبًا جاهزًا</b> بالأسفل وسأبني عليه:"
    )
    return card("📝 <b>فكرة المشروع</b>", body, footer=False)


def idea_keyboard(ptype):
    rows = [[_btn(title, f"tpl:{ptype}:{index}")] for index, (title, _) in enumerate(catalog.type_info(ptype)["templates"])]
    rows.append([_btn("🔙 تغيير النوع", "nav:new"), _btn("❌ إلغاء", "cancel")])
    return _kb(*rows)


def images_text(idea, images_count, template_title=None):
    source = f"🎯 القالب: <b>{esc(template_title)}</b>\n" if template_title else ""
    body = (
        f"{source}📄 <b>الفكرة:</b>\n<i>{esc(short(idea, 350))}</i>\n\n"
        f"🖼 الصور المرفوعة: <b>{images_count}</b> / {config.MAX_IMAGES_PER_PROJECT}\n\n"
        "• أرسل <b>لوجو أو صور</b> (اختياري) — اكتب وصفها في تعليق الصورة.\n"
        "• أرسل <b>رسالة نصية</b> لإضافة تفاصيل للفكرة.\n"
        "• اضغط <b>ابدأ التوليد</b> وقتما تكون جاهزًا."
    )
    return card("📸 <b>الصور والتفاصيل</b>", body, footer=False)


def images_keyboard():
    return _kb(
        [_btn("🚀 ابدأ التوليد الآن", "gen:start")],
        [_btn("❌ إلغاء المشروع", "cancel")],
    )


def modify_text(project):
    body = (
        f"📛 المشروع: <b>{esc(project['name'])}</b>\n"
        f"{catalog.type_label(project['type'])}\n\n"
        "✍️ <b>اكتب التعديلات المطلوبة بالتفصيل</b>\n"
        "مثال: <i>غيّر الألوان للأزرق، أضف قسم أسعار، وأضف زر واتساب عائم.</i>"
    )
    return card("✏️ <b>تعديل المشروع</b>", body, footer=False)


def modify_keyboard(pid):
    return _kb([_btn("🔙 رجوع للمشروع", f"proj:{pid}"), _btn("❌ إلغاء", "cancel")])


def retry_keyboard():
    return _kb([_btn("🔄 حاول تاني", "gen:retry")], [_btn("❌ إلغاء المشروع", "cancel")])


def result_keyboard(ptype, pid):
    return _kb(
        [_btn(catalog.hosting_label(ptype), url=catalog.hosting_url(ptype))],
        [_btn("✏️ تعديل المشروع", f"mod:{pid}"), _btn("📂 مشاريعي", "my:0")],
        [_btn("🚀 مشروع جديد", "nav:new"), _btn("👨‍💻 المطور", "nav:dev")],
    )


def result_caption(name, ptype, files_count, seconds, description="", note="", modified=False, single_file=None):
    if catalog.type_info(ptype)["hosting"] == "web":
        hosting = f"ارفع الموقع على Vercel ({config.WEB_HOSTING_URL})"
    elif catalog.is_single_file(ptype):
        hosting = f"ارفع الملف على بوت الاستضافة وشغّله {config.BOT_HOSTING_URL}"
    else:
        hosting = f"شغّل بوتك عبر بوت الاستضافة {config.BOT_HOSTING_URL}"
    files_line = (
        f"📄 الملف: <code>{esc(single_file)}</code>   ⏱ <b>{seconds}s</b>"
        if single_file
        else f"📄 الملفات: <b>{files_count}</b>   ⏱ <b>{seconds}s</b>"
    )
    lines = [
        f"✅ <b>{'تم تعديل المشروع!' if modified else 'تم إنشاء مشروعك!'}</b>",
        LINE,
        f"📛 <b>{esc(name)}</b>",
        f"🧩 {catalog.type_label(ptype)}",
        files_line,
    ]
    if description:
        lines.append(f"📝 <i>{esc(short(description, 160))}</i>")
    if note:
        lines.append(f"⚠️ {esc(note)}")
    lines += [LINE, f"🚀 <b>الخطوة التالية:</b> {esc(hosting)}", FOOTER]
    return "\n".join(lines)[:1000]


# ----------------------------------------------------------
#  MY PROJECTS
# ----------------------------------------------------------

PAGE_SIZE = 6


def projects_text(total, page):
    if total == 0:
        return card("📂 <b>مشاريعي</b>", "لا توجد مشاريع بعد.\nابدأ أول مشروع لك الآن 🚀")
    pages = max(1, math.ceil(total / PAGE_SIZE))
    return card("📂 <b>مشاريعي</b>", f"إجمالي المشاريع: <b>{total}</b>\nالصفحة <b>{page + 1}</b> من <b>{pages}</b>\n\nاختر مشروعًا:")


def projects_keyboard(projects, total, page):
    rows = []
    for project in projects:
        info = catalog.type_info(project["type"])
        label = f"{info['emoji']} {short(project['name'], 22)} · {pretty_date(project['updated_at'])[:5]}"
        rows.append([_btn(label, f"proj:{project['project_id']}")])

    nav = []
    if page > 0:
        nav.append(_btn("⬅️ السابق", f"my:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(_btn("التالي ➡️", f"my:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([_btn("🚀 مشروع جديد", "nav:new")])
    rows.append(back_home_row())
    return _kb(*rows)


def project_text(project):
    body = (
        f"📛 <b>{esc(project['name'])}</b>\n"
        f"🧩 {catalog.type_label(project['type'])}\n"
        + ("📄 ملف Python واحد" if catalog.is_single_file(project["type"])
           else f"📄 الملفات: <b>{project['files_count']}</b>")
        + f"   🔖 النسخة: <b>v{project['version']}</b>\n"
        f"📅 أُنشئ: {pretty_date(project['created_at'])}   🔄 آخر تعديل: {pretty_date(project['updated_at'])}\n\n"
        f"💡 <i>{esc(short(project['idea'], 220))}</i>"
    )
    return card("📁 <b>تفاصيل المشروع</b>", body)


def project_keyboard(project):
    pid = project["project_id"]
    return _kb(
        [_btn("📄 تحميل الملف" if catalog.is_single_file(project["type"]) else "📦 تحميل ZIP", f"dl:{pid}"),
         _btn("✏️ تعديل بالذكاء", f"mod:{pid}")],
        [_btn(catalog.hosting_label(project["type"]), url=catalog.hosting_url(project["type"]))],
        [_btn("🗑 حذف", f"del:{pid}"), _btn("🔙 مشاريعي", "my:0")],
    )


def delete_confirm_keyboard(pid):
    return _kb([_btn("✅ نعم، احذف", f"delok:{pid}"), _btn("↩️ تراجع", f"proj:{pid}")])


# ----------------------------------------------------------
#  SECTIONS
# ----------------------------------------------------------

def account_text(user, projects_total, used, limit, is_admin):
    quota = "♾ غير محدود (أدمن)" if is_admin else f"{bar(used * 100 // max(limit, 1))} {used}/{limit}"
    body = (
        f"👤 الاسم: <b>{esc(user.get('first_name') or '-')}</b>\n"
        f"🆔 المعرف: <code>{user['user_id']}</code>\n"
        f"📅 انضممت: {pretty_date(user['joined_at'])}\n\n"
        f"📂 مشاريعي: <b>{projects_total}</b>\n"
        f"⚡ استخدام اليوم: {quota}\n"
        f"🎨 ستايل المواقع: {THEME_LABELS.get(user['theme'], user['theme'])}\n"
        f"🌍 لغة المشاريع: {LANG_LABELS.get(user['site_lang'], user['site_lang'])}"
    )
    return card("📊 <b>حسابي</b>", body)


def home_only_keyboard():
    return _kb(back_home_row())


def hosting_text():
    body = (
        "🤖 <b>استضافة البوتات</b>\n"
        "ارفع ملفات بوتك وشغّله وأوقفه بسهولة من بوت الاستضافة.\n"
        f"👉 {config.BOT_HOSTING_URL}\n\n"
        "🌐 <b>استضافة المواقع</b>\n"
        "انشر موقعك على Vercel مع HTTPS تلقائي ورابط جاهز للمشاركة.\n"
        f"👉 {config.WEB_HOSTING_URL}\n\n"
        "📦 كل مشروع يصلك داخل ZIP فيه <b>HOSTING_GUIDE.md</b> بخطوات الرفع."
    )
    return card("🖥 <b>الاستضافة</b>", body)


def hosting_keyboard():
    return _kb(
        [_btn("🤖 استضافة البوتات", url=config.BOT_HOSTING_URL)],
        [_btn("🌐 استضافة المواقع (Vercel)", url=config.WEB_HOSTING_URL)],
        [_btn("📘 خطوات نشر موقع", "host:web"), _btn("📗 خطوات تشغيل بوت", "host:bot")],
        back_home_row(),
    )


def host_steps_text(kind):
    if kind == "web":
        body = (
            "1️⃣ أنشئ حسابًا على Vercel.\n"
            "2️⃣ ارفع مجلد الموقع إلى GitHub.\n"
            "3️⃣ في Vercel: <b>Add New ← Project</b> واختر المستودع.\n"
            "4️⃣ اترك الإعدادات الافتراضية واضغط <b>Deploy</b>.\n"
            "5️⃣ يصبح موقعك متاحًا على رابط <code>.vercel.app</code> ✅\n\n"
            "💡 تأكد أن <code>index.html</code> في جذر المشروع."
        )
        return card("📘 <b>نشر موقع على Vercel</b>", body)
    body = (
        f"1️⃣ افتح بوت الاستضافة {config.BOT_HOSTING_URL}\n"
        "2️⃣ فك ضغط ملف المشروع على جهازك.\n"
        "3️⃣ ضع التوكن/المفاتيح داخل ملف الإعدادات.\n"
        "4️⃣ ارفع الملف الرئيسي والملفات المساعدة.\n"
        "5️⃣ شغّل البوت من لوحة التحكم ✅\n\n"
        "💡 تأكد من وجود <code>requirements.txt</code> وأن التوكن صحيح."
    )
    return card("📗 <b>تشغيل بوت على الاستضافة</b>", body)


def host_steps_keyboard():
    return _kb([_btn("🔙 الاستضافة", "nav:host")], back_home_row())


def features_text():
    body = (
        "🧠 ذكاء اصطناعي متقدم (Gemini) لبناء مشاريع كاملة\n"
        "🌐 مواقع • 🤖 بوتات تيليجرام وديسكورد • 🐍 أدوات Python\n"
        "⚡ قوالب جاهزة لكل نوع لبدء سريع\n"
        "🖼 رفع الشعار والصور وإدراجها داخل المشروع\n"
        "✏️ تعديل أي مشروع سابق بطلب نصي بسيط\n"
        "📂 أرشيف مشاريعك وتحميلها في أي وقت\n"
        "🎨 اختيار ستايل المواقع ولغة المشروع\n"
        "📦 ملف ZIP منظم + README + دليل استضافة (وملف .py مباشر لأدوات Python)\n"
        "🎬 شريط تقدم متحرك أثناء التوليد\n"
        "🛡 نظام حدود يومية وطابور عادل للجميع"
    )
    return card("💎 <b>المميزات</b>", body)


def help_text():
    body = (
        "<b>طريقة الاستخدام:</b>\n"
        "1️⃣ اضغط <b>إنشاء مشروع جديد</b> واختر النوع.\n"
        "2️⃣ اكتب فكرتك أو اختر قالبًا جاهزًا.\n"
        "3️⃣ أضف صورًا (اختياري) ثم <b>ابدأ التوليد</b>.\n"
        "4️⃣ استلم ملف ZIP جاهزًا للرفع 🚀\n\n"
        "<b>نصائح لنتيجة أقوى:</b>\n"
        "• حدّد الأقسام والمزايا بدقة.\n"
        "• اذكر الألوان والستايل وأمثلة تعجبك.\n"
        "• عدّل المشروع بعد التوليد بطلبات صغيرة واضحة.\n\n"
        "<b>الأوامر:</b>\n"
        "/start القائمة • /new مشروع جديد • /projects مشاريعي\n"
        "/account حسابي • /hosting الاستضافة • /developer المطور\n"
        "/cancel إلغاء"
    )
    return card("📖 <b>المساعدة</b>", body)


def developer_text():
    body = (
        f"👤 <b>{esc(config.DEVELOPER_NAME)}</b>\n"
        f"🏷 العلامة: <b>{esc(config.BOT_NAME)}</b>\n"
        "🧑‍💻: مطور مواقع و هكر اخلاقي\n\n"
        "<b>الخدمات:</b>\n"
        "مطور مواقع 🌐\n"
        "مطور سوفت ويير 👾\n"
        "متخصص بايثون 🐍\n"
        "هكر اخلاقي وامن سبراني 🖥👨‍💻\n"
        "📩 للطلبات الخاصة والتعاون تواصل معي مباشرة:"
    )
    return card("👨‍💻 <b>المطور</b>", body)


def developer_keyboard():
    return _kb(
        contact_row(),
        [_btn("🤖 استضافة البوتات", url=config.BOT_HOSTING_URL), _btn("🌐 Vercel", url=config.WEB_HOSTING_URL)],
        back_home_row(),
    )


def maintenance_keyboard():
    return _kb(contact_row())


def settings_text(user):
    body = (
        "تُطبَّق هذه الإعدادات على كل مشروع جديد.\n\n"
        f"🎨 ستايل المواقع: <b>{THEME_LABELS.get(user['theme'])}</b>\n"
        f"🌍 لغة المشروع: <b>{LANG_LABELS.get(user['site_lang'])}</b>"
    )
    return card("⚙️ <b>الإعدادات</b>", body)


def settings_keyboard(user):
    theme_row = [
        _btn(("✅ " if user["theme"] == key else "") + label, f"set:theme:{key}")
        for key, label in THEME_LABELS.items()
    ]
    lang_row = [
        _btn(("✅ " if user["site_lang"] == key else "") + label, f"set:lang:{key}")
        for key, label in LANG_LABELS.items()
    ]
    return _kb(theme_row, lang_row, back_home_row())


# ----------------------------------------------------------
#  GATES  (maintenance / forced subscription)
# ----------------------------------------------------------

def maintenance_text():
    body = (
        "🛠 البوت في <b>صيانة مؤقتة</b> لتحسين الخدمة.\n"
        "سنعود قريبًا بأفضل شكل ⚡\n\n"
        f"📩 للاستفسار: @{esc(config.CONTACT_TELEGRAM)}"
    )
    return card("🔒 <b>وضع الصيانة</b>", body)


def subscribe_text():
    body = (
        "للاستفادة من البوت اشترك في قناتنا أولًا،\n"
        "ثم اضغط <b>✅ تحققت من الاشتراك</b>."
    )
    return card("🔒 <b>الاشتراك الإجباري</b>", body)


def subscribe_keyboard(link):
    rows = []
    if link:
        rows.append([_btn("📢 اشترك في القناة", url=link)])
    rows.append([_btn("✅ تحققت من الاشتراك", "chk:sub")])
    return _kb(*rows)


def admin_stats_block(stats):
    types_line = " • ".join(f"{catalog.type_label(k)} {v}" for k, v in stats["by_type"]) or "-"
    top = "\n".join(
        f"{i}. {esc(name or '-')} {('@' + esc(username)) if username else ''} — <b>{total}</b>"
        for i, (_, name, username, total) in enumerate(stats["top_users"], 1)
    ) or "-"
    return (
        "🏭 <b>المشاريع</b>\n"
        f"📦 الإجمالي: <b>{stats['projects']}</b> (اليوم {stats['projects_today']})\n"
        f"⚡ عمليات توليد اليوم: <b>{stats['generations_today']}</b>\n"
        f"👥 مستخدمون جدد اليوم: <b>{stats['users_today']}</b>\n"
        f"🧩 الأنواع: {types_line}\n\n"
        f"🏆 <b>الأكثر نشاطًا:</b>\n{top}"
    )


# ----------------------------------------------------------
#  ANIMATIONS
# ----------------------------------------------------------

def play_startup_animation(bot, chat_id):
    """Short boot animation; returns the message to turn into the welcome card."""
    frames = [
        ("⚡", 8, "تهيئة النظام"),
        ("🧠", 34, "تحميل محرك الذكاء الاصطناعي"),
        ("🛠", 62, "تجهيز مصنع المشاريع"),
        ("🚀", 88, "ضبط الاستضافة والقوالب"),
        ("✅", 100, "جاهز للانطلاق"),
    ]
    message = None
    for icon, percent, label in frames:
        text = (
            f"{icon} <b>{config.BOT_NAME.upper()}</b>\n{LINE}\n"
            f"{bar(percent)} <b>{percent}%</b>\n<i>{label}...</i>"
        )
        try:
            if message is None:
                message = bot.send_message(chat_id, text)
            else:
                bot.edit_message_text(text, chat_id, message.message_id)
        except Exception as error:
            log.debug("animation frame skipped: %s", error)
        time.sleep(0.55)
    return message


class ProgressAnimator(object):
    """Edits one message every ~2 seconds while the AI is working."""

    STAGES = [
        ("🧠", "فهم الفكرة وتحليل المتطلبات", 0),
        ("🏗", "تصميم هيكل المشروع", 18),
        ("⌨️", "كتابة الأكواد والملفات", 38),
        ("🔍", "مراجعة الجودة والتنسيق", 72),
        ("📦", "تجهيز الملفات وضغطها", 90),
    ]
    SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, bot, chat_id, message_id, title, expected_seconds=70):
        self.bot, self.chat_id, self.message_id = bot, chat_id, message_id
        self.title = title
        self.expected = float(expected_seconds)
        self.queued = False
        self.percent = 0
        self._stop = threading.Event()
        self._thread = None
        self._started_at = time.time()
        self._tick = 0
        self._last_text = ""

    # -- rendering ------------------------------------------------
    def _render(self):
        if self.queued:
            return (
                f"⏳ <b>{esc(self.title)}</b>\n{LINE}\n"
                "🚦 طلبك في الطابور...\n"
                "<i>هيبدأ تلقائيًا أول ما يخلص مشروع شغال حاليًا.</i>"
            )

        elapsed = time.time() - self._started_at
        self.percent = max(self.percent, int(92 * (1 - math.exp(-elapsed / self.expected))))
        spin = self.SPIN[self._tick % len(self.SPIN)]
        current = max(i for i, stage in enumerate(self.STAGES) if self.percent >= stage[2])

        lines = []
        for index, (icon, label, _) in enumerate(self.STAGES):
            if index < current:
                lines.append(f"✅ {label}")
            elif index == current:
                lines.append(f"{spin} <b>{label}</b> {icon}")
            else:
                lines.append(f"▫️ <i>{label}</i>")

        return (
            f"🎬 <b>{esc(self.title)}</b>\n{LINE}\n" + "\n".join(lines) + f"\n{LINE}\n"
            f"{bar(self.percent)} <b>{self.percent}%</b>   ⏱ {int(elapsed)}s"
        )

    def _edit(self, text, markup=None):
        if text == self._last_text:
            return
        try:
            self.bot.edit_message_text(text, self.chat_id, self.message_id, reply_markup=markup)
            self._last_text = text
        except Exception as error:
            if "message is not modified" not in str(error):
                log.debug("progress edit skipped: %s", error)

    def _run(self):
        while not self._stop.wait(2.0):
            self._tick += 1
            self._edit(self._render())

    # -- control --------------------------------------------------
    def start(self):
        self._edit(self._render())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def reset_clock(self):
        self._started_at = time.time()
        self.percent = 0

    def _halt(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def stage_packaging(self):
        self.percent = max(self.percent, 90)

    def finish(self, text):
        self._halt()
        self._edit(text)

    def fail(self, text, markup=None):
        self._halt()
        self._edit(text, markup)

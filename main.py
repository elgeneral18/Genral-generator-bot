# ==========================================================
#  DARK ELGENERAL — AI Project Generator Bot
#  Websites • Telegram bots • Discord bots • Python tools
# ----------------------------------------------------------
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
#  All rights reserved.
# ==========================================================

import os
import re
import shutil
import sys
import threading
import time
import uuid

import config

# Always run relative to this file (hosting panels often start from another cwd)
os.chdir(config.BASE_DIR)

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

import admin_panel
import ai_client
import ai_generator
import catalog
import database as db
import project_writer
import sessions
import ui
import zip_builder
from utils import esc, human_size, log, setup_logging, short, slugify


setup_logging()

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=16)

gen_slots = threading.BoundedSemaphore(config.MAX_CONCURRENT_GENERATIONS)
_sub_cache = {}           # user_id -> time until which "subscribed" is trusted
_sub_warned = [False]

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
MAX_TELEGRAM_FILE = 49 * 1024 * 1024


class GenError(Exception):
    """Generation failure with a user-friendly message and a technical detail."""

    def __init__(self, public, detail=""):
        Exception.__init__(self, detail or public)
        self.public = public
        self.detail = detail or public


# ==========================================================
#  ADMIN PANEL  (registered first so its handlers take priority)
# ==========================================================

def _extra_admin_stats():
    return ui.admin_stats_block(db.get_stats())


def _after_panel(chat_id):
    bot.send_message(chat_id, ui.welcome_text("أدمن"), reply_markup=ui.main_menu())


panel = admin_panel.setup_admin(bot, config.ADMIN_ID, extra_stats=_extra_admin_stats, on_back=_after_panel)


# ==========================================================
#  HELPERS
# ==========================================================

def is_admin(user_id):
    return user_id == config.ADMIN_ID


def notify_admin(text):
    if not config.ADMIN_NOTIFICATIONS:
        return
    try:
        bot.send_message(config.ADMIN_ID, text)
    except Exception as error:
        log.debug("admin notify skipped: %s", error)


def user_link(user):
    link = f'<a href="tg://user?id={user.id}">{esc(user.first_name or "-")}</a>'
    return link + (f" @{esc(user.username)}" if user.username else "")


def view(chat_id, message_id, text, markup=None):
    """Edit a message in place; fall back to a new message when impossible."""
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            return
        except ApiTelegramException as error:
            if "message is not modified" in str(error):
                return
        except Exception as error:
            log.debug("edit fallback: %s", error)
    bot.send_message(chat_id, text, reply_markup=markup)


def subscription_gate(user, chat_id, send_prompt=True):
    """Forced channel subscription. Returns True when the user may continue."""
    if is_admin(user.id) or not panel.get_channel_username():
        return True
    if _sub_cache.get(user.id, 0) > time.time():
        return True

    status = panel.is_subscribed(user.id)
    if status is None:
        # Cannot verify (bot is not admin in the channel / wrong ID): do not lock users out
        if not _sub_warned[0]:
            _sub_warned[0] = True
            notify_admin("⚠️ <b>تعذّر فحص الاشتراك الإجباري</b>\nتأكد أن البوت <b>أدمن</b> في القناة وأن المعرف صحيح.")
        return True
    if status:
        _sub_cache[user.id] = time.time() + 60
        return True

    if send_prompt:
        try:
            bot.send_message(chat_id, ui.subscribe_text(), reply_markup=ui.subscribe_keyboard(panel.get_channel_link()))
        except Exception:
            pass
    return False


def guard(user, chat_id, check_subscription=True, send_prompt=True):
    """Register the user; enforce bans, maintenance mode and forced subscription."""
    if db.upsert_user(user) and panel.is_notify_enabled():
        try:
            bot.send_message(config.ADMIN_ID, f"👤 <b>مستخدم جديد</b>\n{user_link(user)}\n🆔 <code>{user.id}</code>")
        except Exception:
            pass

    if is_admin(user.id):
        return True

    if db.is_banned(user.id):
        try:
            bot.send_message(
                chat_id,
                "🚫 <b>تم حظرك من استخدام البوت.</b>\n"
                f"للاستفسار تواصل مع @{esc(config.CONTACT_TELEGRAM)}",
            )
        except Exception:
            pass
        return False

    if panel.is_maintenance():
        try:
            bot.send_message(chat_id, ui.maintenance_text(), reply_markup=ui.maintenance_keyboard())
        except Exception:
            pass
        return False

    if check_subscription and not subscription_gate(user, chat_id, send_prompt):
        return False
    return True


def check_allowed(user_id):
    if is_admin(user_id):
        return True, ""
    if db.get_usage_today(user_id) >= config.DAILY_LIMIT:
        return False, (
            f"🚫 وصلت للحد اليومي ({config.DAILY_LIMIT} مشاريع). "
            f"جرّب غدًا أو تواصل مع @{config.CONTACT_TELEGRAM}"
        )
    left = db.cooldown_left(user_id)
    if left > 0:
        return False, f"⏱ استنى {left} ثانية قبل مشروعك التالي."
    return True, ""


def safe_project_path(path):
    root = os.path.realpath(config.PROJECTS_DIR)
    target = os.path.realpath(path or "")
    return target if target.startswith(root + os.sep) else None


# ==========================================================
#  SECTIONS  (used by both commands and buttons)
# ==========================================================

def show_section(section, user, chat_id, message_id=None, page=0):
    uid = user.id

    if section == "main":
        view(chat_id, message_id, ui.welcome_text(user.first_name or "صديقي"), ui.main_menu())

    elif section == "new":
        view(chat_id, message_id, ui.type_chooser_text(), ui.type_chooser_keyboard())

    elif section == "account":
        record = db.get_user(uid)
        text = ui.account_text(record, db.count_projects(uid), db.get_usage_today(uid),
                               config.DAILY_LIMIT, is_admin(uid))
        view(chat_id, message_id, text, ui.home_only_keyboard())

    elif section == "projects":
        total = db.count_projects(uid)
        last_page = max(0, (total - 1) // ui.PAGE_SIZE)
        page = max(0, min(page, last_page))
        items = db.list_projects(uid, ui.PAGE_SIZE, page * ui.PAGE_SIZE)
        view(chat_id, message_id, ui.projects_text(total, page), ui.projects_keyboard(items, total, page))

    elif section == "host":
        view(chat_id, message_id, ui.hosting_text(), ui.hosting_keyboard())

    elif section == "features":
        view(chat_id, message_id, ui.features_text(), ui.home_only_keyboard())

    elif section == "dev":
        view(chat_id, message_id, ui.developer_text(), ui.developer_keyboard())

    elif section == "help":
        view(chat_id, message_id, ui.help_text(), ui.home_only_keyboard())

    elif section == "settings":
        record = db.get_user(uid)
        view(chat_id, message_id, ui.settings_text(record), ui.settings_keyboard(record))


# ==========================================================
#  COMMANDS
# ==========================================================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    if not guard(message.from_user, message.chat.id):
        return
    bot.send_chat_action(message.chat.id, "typing")
    animation = ui.play_startup_animation(bot, message.chat.id)
    show_section("main", message.from_user, message.chat.id,
                 animation.message_id if animation else None)


def _command_section(section):
    def handler(message):
        if guard(message.from_user, message.chat.id):
            show_section(section, message.from_user, message.chat.id)
    return handler


for _command, _section in (
    ("menu", "main"), ("new", "new"), ("account", "account"), ("projects", "projects"),
    ("hosting", "host"), ("developer", "dev"), ("help", "help"),
    ("settings", "settings"),
):
    bot.message_handler(commands=[_command])(_command_section(_section))


@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    if not guard(message.from_user, message.chat.id):
        return
    uid = message.from_user.id
    panel.clear_state(uid)
    session = sessions.get(uid)
    if session and session.get("busy"):
        bot.send_message(message.chat.id, "⏳ المشروع لسه بيتعمل، استنى لحد ما يخلص.")
        return
    sessions.clear(uid)
    bot.send_message(message.chat.id, "❌ <b>تم الإلغاء.</b>", reply_markup=ui.main_menu())


# ==========================================================
#  CALLBACKS
# ==========================================================

@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    user = call.from_user
    answered = [False]

    def ack(text=None, alert=False):
        if answered[0]:
            return
        answered[0] = True
        try:
            bot.answer_callback_query(call.id, text=text, show_alert=alert)
        except Exception:
            pass

    try:
        chat_id = call.message.chat.id

        if call.data == "chk:sub":
            _sub_cache.pop(user.id, None)
            if guard(user, chat_id, send_prompt=False):
                ack("✅ تم التحقق، أهلاً بك!")
                show_section("main", user, chat_id, call.message.message_id)
            else:
                ack("❌ لم يتم العثور على اشتراكك بعد.", True)
            return

        if not guard(user, chat_id):
            ack()
            return
        handle_callback(call, user, chat_id, call.message.message_id, call.data or "", ack)
    except Exception:
        log.exception("callback error (%s)", call.data)
        ack("⚠️ حصل خطأ، حاول تاني.", True)
    finally:
        ack()


def handle_callback(call, user, chat_id, message_id, data, ack):
    uid = user.id
    parts = data.split(":")
    action = parts[0]
    session = sessions.get(uid)

    # ---------- navigation ----------
    if action == "nav":
        ack()
        show_section(parts[1], user, chat_id, message_id)

    elif action == "my":
        ack()
        show_section("projects", user, chat_id, message_id, page=int(parts[1]))

    elif action == "host":
        ack()
        view(chat_id, message_id, ui.host_steps_text(parts[1]), ui.host_steps_keyboard())

    # ---------- settings ----------
    elif action == "set":
        key, value = parts[1], parts[2]
        if key == "theme" and value in ui.THEME_LABELS:
            db.set_setting(uid, "theme", value)
        elif key == "lang" and value in ui.LANG_LABELS:
            db.set_setting(uid, "site_lang", value)
        ack("✅ تم الحفظ")
        show_section("settings", user, chat_id, message_id)

    # ---------- new project ----------
    elif action == "type":
        if session and session.get("busy"):
            ack("⏳ عندك مشروع قيد التوليد حاليًا.", True)
            return
        ptype = parts[1]
        if ptype not in catalog.PROJECT_TYPES:
            ack()
            return
        ack()
        sessions.start(uid, ptype)
        view(chat_id, message_id, ui.idea_text(ptype), ui.idea_keyboard(ptype))

    elif action == "tpl":
        if session and session.get("busy"):
            ack("⏳ عندك مشروع قيد التوليد حاليًا.", True)
            return
        ptype, index = parts[1], int(parts[2])
        templates = catalog.type_info(ptype)["templates"]
        if ptype not in catalog.PROJECT_TYPES or index >= len(templates):
            ack()
            return
        if not session or session["mode"] != "new" or session["type"] != ptype:
            session = sessions.start(uid, ptype)
        title, idea = templates[index]
        session["idea"] = idea
        session["step"] = "images"
        ack("✅ تم اختيار القالب")
        view(chat_id, message_id, ui.images_text(idea, len(session["images"]), title), ui.images_keyboard())

    elif action == "gen":
        if parts[1] == "start":
            begin_generation(uid, chat_id, user, ("images", "request"), ack)
        elif parts[1] == "retry":
            begin_generation(uid, chat_id, user, ("failed",), ack)

    elif action == "cancel":
        if session and session.get("busy"):
            ack("⏳ المشروع لسه بيتعمل، استنى لحد ما يخلص.", True)
            return
        sessions.clear(uid)
        panel.clear_state(uid)
        ack("❌ تم الإلغاء")
        show_section("main", user, chat_id, message_id)

    # ---------- my projects ----------
    elif action == "proj":
        project = db.get_project(parts[1], uid)
        if not project:
            ack("❌ المشروع غير موجود.", True)
            return
        ack()
        view(chat_id, message_id, ui.project_text(project), ui.project_keyboard(project))

    elif action == "dl":
        project = db.get_project(parts[1], uid)
        if not project:
            ack("❌ المشروع غير موجود.", True)
            return
        ack("📦 جاري تجهيز الملف...")
        try:
            send_project(chat_id, project, download_caption(project), ui.project_keyboard(project))
        except GenError as error:
            bot.send_message(chat_id, error.public)
        except Exception:
            log.exception("download error")
            bot.send_message(chat_id, "⚠️ تعذّر تجهيز الملف، حاول مرة أخرى.")

    elif action == "mod":
        project = db.get_project(parts[1], uid)
        if not project:
            ack("❌ المشروع غير موجود.", True)
            return
        if session and session.get("busy"):
            ack("⏳ عندك مشروع قيد التوليد حاليًا.", True)
            return
        if not os.path.isdir(project["path"]):
            ack("⚠️ ملفات المشروع لم تعد موجودة على السيرفر.", True)
            return
        ack()
        sessions.start(uid, project["type"], mode="modify", project=project)
        view(chat_id, message_id, ui.modify_text(project), ui.modify_keyboard(project["project_id"]))

    elif action == "del":
        project = db.get_project(parts[1], uid)
        if not project:
            ack("❌ المشروع غير موجود.", True)
            return
        ack()
        view(chat_id, message_id,
             f"🗑 <b>حذف المشروع؟</b>\n\n📛 {esc(project['name'])}\n\nلا يمكن التراجع عن الحذف.",
             ui.delete_confirm_keyboard(project["project_id"]))

    elif action == "delok":
        project = db.get_project(parts[1], uid)
        if project:
            db.delete_project(project["project_id"], uid)
            target = safe_project_path(project["path"])
            if target:
                shutil.rmtree(target, ignore_errors=True)
        ack("🗑 تم الحذف")
        show_section("projects", user, chat_id, message_id)

    else:
        ack()


# ==========================================================
#  TEXT / MEDIA INPUT
# ==========================================================

@bot.message_handler(content_types=["text"])
def on_text(message):
    user, chat_id = message.from_user, message.chat.id
    if not guard(user, chat_id):
        return

    uid = user.id
    text = (message.text or "").strip()

    if text.startswith("/"):
        bot.send_message(chat_id, "❓ أمر غير معروف. استخدم /menu لعرض القائمة.")
        return

    session = sessions.get(uid)
    if not session:
        bot.send_message(chat_id, "👋 اختر من القائمة للبدء:", reply_markup=ui.main_menu())
        return

    step = session["step"]

    if step == "idea":
        if len(text) < 15:
            bot.send_message(chat_id, "⚠️ الفكرة قصيرة جدًا. اكتب تفاصيل أكثر (15 حرف على الأقل).")
            return
        session["idea"] = text[:3000]
        session["step"] = "images"
        bot.send_message(chat_id, ui.images_text(session["idea"], len(session["images"])),
                         reply_markup=ui.images_keyboard())

    elif step == "images":
        session["idea"] = (session["idea"] + "\n" + text)[:3500]
        bot.send_message(chat_id, "📝 <b>تمت إضافة التفاصيل للفكرة.</b>\n\n" +
                         ui.images_text(session["idea"], len(session["images"])),
                         reply_markup=ui.images_keyboard())

    elif step == "request":
        if len(text) < 8:
            bot.send_message(chat_id, "⚠️ اكتب التعديل المطلوب بتفصيل أكثر.")
            return
        session["idea"] = text[:3000]
        begin_generation(uid, chat_id, user, ("request",), lambda *a, **k: None)

    elif step == "generating":
        bot.send_message(chat_id, "⏳ المشروع لسه بيتعمل، استنى شوية...")

    elif step == "failed":
        bot.send_message(chat_id, "⚠️ آخر محاولة فشلت. اضغط «حاول تاني» أو ألغِ المشروع.",
                         reply_markup=ui.retry_keyboard())


def save_incoming_image(message, file_id, extension, caption):
    user, chat_id = message.from_user, message.chat.id
    if not guard(user, chat_id):
        return

    session = sessions.get(user.id)
    if not session or session["step"] != "images":
        bot.reply_to(message, "⚠️ ابدأ مشروعًا جديدًا أولًا، ثم أرسل الصور بعد كتابة الفكرة.",
                     reply_markup=ui.main_menu())
        return

    if len(session["images"]) >= config.MAX_IMAGES_PER_PROJECT:
        bot.reply_to(message, f"⚠️ وصلت للحد الأقصى ({config.MAX_IMAGES_PER_PROJECT} صور).",
                     reply_markup=ui.images_keyboard())
        return

    try:
        info = bot.get_file(file_id)
        if info.file_size and info.file_size > config.MAX_IMAGE_MB * 1024 * 1024:
            bot.reply_to(message, f"⚠️ الصورة كبيرة جدًا (الحد {config.MAX_IMAGE_MB} MB).")
            return

        content = bot.download_file(info.file_path)

        if not extension:
            path = info.file_path or ""
            extension = ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ".jpg"
        if extension not in IMAGE_EXTENSIONS:
            extension = ".jpg"

        name = f"img_{int(time.time())}_{uuid.uuid4().hex[:4]}{extension}"
        os.makedirs(session["images_dir"], exist_ok=True)
        with open(os.path.join(session["images_dir"], name), "wb") as handle:
            handle.write(content)

        session["images"].append({"name": name, "desc": short(caption or "", 120)})

        bot.send_message(
            message.chat.id,
            f"✅ <b>تم حفظ الصورة</b> ({len(session['images'])}/{config.MAX_IMAGES_PER_PROJECT})\n"
            f"📁 <code>images/{name}</code>\n\nأرسل المزيد أو اضغط <b>ابدأ التوليد</b>.",
            reply_markup=ui.images_keyboard(),
        )
    except Exception:
        log.exception("image error")
        bot.reply_to(message, "❌ تعذّر حفظ الصورة، جرّب مرة أخرى.")


@bot.message_handler(content_types=["photo"])
def on_photo(message):
    save_incoming_image(message, message.photo[-1].file_id, "", message.caption)


@bot.message_handler(content_types=["document"])
def on_document(message):
    document = message.document
    extension = os.path.splitext((document.file_name or "").lower())[1]
    if extension not in IMAGE_EXTENSIONS:
        if guard(message.from_user, message.chat.id):
            bot.reply_to(message, "⚠️ أقبل ملفات الصور فقط (JPG / PNG / WEBP / GIF).")
        return
    save_incoming_image(message, document.file_id, extension, message.caption)


@bot.message_handler(content_types=["sticker", "video", "audio", "voice", "video_note", "location", "contact"])
def on_unsupported(message):
    if guard(message.from_user, message.chat.id):
        bot.reply_to(message, "⚠️ هذا النوع من الرسائل غير مدعوم. أرسل نصًا أو صورة.")


# ==========================================================
#  GENERATION
# ==========================================================

def begin_generation(uid, chat_id, user, from_steps, ack):
    session = sessions.get(uid)
    if not session:
        ack("⌛ انتهت الجلسة، ابدأ مشروعًا جديدًا.", True)
        return
    if session["busy"] or session["step"] == "generating":
        ack("⏳ المشروع لسه بيتعمل، استنى شوية.", True)
        return
    if session["step"] not in from_steps:
        ack()
        return
    if not session["idea"].strip():
        ack("✍️ اكتب فكرة المشروع أولًا.", True)
        return

    allowed, reason = check_allowed(uid)
    if not allowed:
        ack(reason, True)
        bot.send_message(chat_id, reason)
        return

    if not sessions.transition(uid, from_steps, "generating"):
        ack()
        return

    session["busy"] = True
    ack("🚀 بدأنا التوليد!")
    threading.Thread(target=generation_worker, args=(uid, chat_id, user), daemon=True).start()


def download_caption(project):
    if catalog.is_single_file(project["type"]):
        detail = "📄 ملف Python واحد"
    else:
        detail = f"📄 {project['files_count']} ملف"
    return (
        f"📦 <b>{esc(project['name'])}</b>\n{catalog.type_label(project['type'])}\n"
        f"{detail} • v{project['version']}\n{ui.FOOTER}"
    )


def single_python_file(project):
    """Path of the only .py file of a python_tool project (None when not applicable)."""
    if not catalog.is_single_file(project["type"]):
        return None
    found = []
    for folder, dirs, names in os.walk(project["path"]):
        dirs[:] = [d for d in dirs if d not in ("images", "assets", "__pycache__")]
        found.extend(os.path.join(folder, n) for n in names if n.lower().endswith(".py"))
    return found[0] if len(found) == 1 else None


def send_project(chat_id, project, caption, markup=None):
    """Python tools are sent as a single .py file; everything else as a ZIP."""
    py_file = single_python_file(project)
    if py_file:
        bot.send_chat_action(chat_id, "upload_document")
        with open(py_file, "rb") as handle:
            bot.send_document(chat_id, handle, caption=caption, reply_markup=markup,
                              visible_file_name=slugify(project["name"]) + ".py")
        return

    zip_path = zip_builder.build_zip(project["path"], project["name"], project["type"])
    try:
        if os.path.getsize(zip_path) > MAX_TELEGRAM_FILE:
            raise GenError("📦 حجم المشروع كبير جدًا للإرسال عبر تيليجرام (الحد 50MB).")
        bot.send_chat_action(chat_id, "upload_document")
        with open(zip_path, "rb") as handle:
            bot.send_document(chat_id, handle, caption=caption, reply_markup=markup,
                              visible_file_name=slugify(project["name"]) + ".zip")
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass


def run_generation(uid, session, animator):
    """Talk to the AI, write the files and register the project. Returns a dict."""
    record = db.get_user(uid) or {}
    options = {"theme": record.get("theme", "dark"), "site_lang": record.get("site_lang", "ar")}
    ptype, mode = session["type"], session["mode"]

    if mode == "modify":
        project = db.get_project(session["project_id"], uid)
        if not project or not os.path.isdir(project["path"]):
            raise GenError("⚠️ ملفات المشروع غير موجودة. أنشئ مشروعًا جديدًا.")
        existing = project_writer.read_project_files(project["path"])
        if not existing:
            raise GenError("⚠️ لا توجد ملفات نصية قابلة للتعديل في هذا المشروع.")
        prompt = ai_generator.build_modify_prompt(ptype, existing, session["idea"], session["images"], options)
    else:
        prompt = ai_generator.build_prompt(ptype, session["idea"], session["images"], options)

    result = ai_client.generate(prompt)
    if not result["success"]:
        raise GenError("⚠️ حصلت مشكلة مؤقتة في محرك الذكاء الاصطناعي. حاول مرة تانية بعد لحظات.",
                       result["error"])

    parsed = ai_generator.parse_response(result["text"], require_name=(mode == "new"))
    if not parsed["success"]:
        raise GenError("⚠️ الرد جه غير مكتمل. جرّب تاني أو اختصر الفكرة شوية.", parsed["error"])

    animator.stage_packaging()

    project_dir = session["project_dir"]
    written = project_writer.write_files(project_dir, parsed["files"], parsed.get("delete"))
    if not written:
        raise GenError("⚠️ لم يتم إنشاء أي ملفات. حاول مرة أخرى.", "no files written")

    if config.ADD_CREDIT_FILE and catalog.is_single_file(ptype):
        py_file = single_python_file({"type": ptype, "path": project_dir})
        if py_file:
            project_writer.add_credit_header(py_file, catalog.credit_header())

    files_count = project_writer.count_files(project_dir)
    session["saved"] = True

    if mode == "modify":
        db.update_project(project["project_id"], files_count)
    else:
        db.add_project(session["project_id"], uid, parsed["project_name"], ptype,
                       session["idea"], project_dir, files_count)

    saved = db.get_project(session["project_id"], uid)
    note = ""
    if parsed.get("truncated") or result.get("truncated"):
        note = "المشروع كبير؛ تم استرجاع الملفات المكتملة فقط. اطلب تعديلًا لإكمال الباقي."
    return {"project": saved, "parsed": parsed, "note": note}


def generation_worker(uid, chat_id, user):
    session = sessions.get(uid)
    if not session:
        return

    started = time.time()
    ptype, mode = session["type"], session["mode"]
    title = "جاري تعديل مشروعك" if mode == "modify" else f"جاري بناء {catalog.type_info(ptype)['title']}"

    status = bot.send_message(chat_id, f"🎬 <b>{esc(title)}</b>\n{ui.LINE}\n⏳ جاري البدء...")
    animator = ui.ProgressAnimator(bot, chat_id, status.message_id, title)
    slot = False

    try:
        if gen_slots.acquire(False):
            slot = True
            animator.start()
        else:
            animator.queued = True
            animator.start()
            gen_slots.acquire()
            slot = True
            animator.queued = False
            animator.reset_clock()

        outcome = run_generation(uid, session, animator)
        project = outcome["project"]
        seconds = int(time.time() - started)

        db.register_generation(uid)
        animator.finish(
            f"✅ <b>اكتمل التوليد!</b>\n{ui.LINE}\n{ui.bar(100)} <b>100%</b>   ⏱ {seconds}s\n📦 جاري إرسال الملف..."
        )

        single = single_python_file(project)
        caption = ui.result_caption(project["name"], ptype, project["files_count"], seconds,
                                    outcome["parsed"]["description"], outcome["note"],
                                    modified=(mode == "modify"),
                                    single_file=(slugify(project["name"]) + ".py") if single else None)
        try:
            send_project(chat_id, project, caption, ui.result_keyboard(ptype, project["project_id"]))
        except GenError as error:
            bot.send_message(chat_id, error.public)
        except Exception:
            log.exception("send zip failed")
            bot.send_message(chat_id, "⚠️ المشروع اتحفظ لكن تعذّر إرسال الملف. افتحه من «مشاريعي» وحمّله.",
                             reply_markup=ui.main_menu())

        notify_admin(
            f"{'✏️ تعديل مشروع' if mode == 'modify' else '📦 مشروع جديد'}\n"
            f"👤 {user_link(user)}\n🧩 {catalog.type_label(ptype)}\n"
            f"📝 {esc(short(session['idea'], 200))}\n📄 {project['files_count']} ملف • ⏱ {seconds}s"
        )
        session["busy"] = False
        sessions.clear(uid, force=True)

    except Exception as error:
        public = error.public if isinstance(error, GenError) else "⚠️ حصل خطأ غير متوقع أثناء التوليد."
        detail = error.detail if isinstance(error, GenError) else repr(error)
        log.error("generation failed for %s: %s", uid, detail)
        if not isinstance(error, GenError):
            log.exception("generation crash")

        animator.fail(f"❌ <b>فشل التوليد</b>\n{ui.LINE}\n{public}", ui.retry_keyboard())
        session["busy"] = False
        sessions.set_step(uid, "failed")
        notify_admin(f"⚠️ <b>فشل توليد</b>\n👤 {user_link(user)}\n<code>{esc(short(detail, 300))}</code>")

    finally:
        if slot:
            gen_slots.release()


# ==========================================================
#  STARTUP
# ==========================================================

def main():
    log.info("=" * 46)
    log.info("%s v%s — AI Project Generator", config.BOT_NAME, config.BOT_VERSION)
    log.info(config.COPYRIGHT)
    log.info("Python %s | data dir: %s", sys.version.split()[0], config.DATA_DIR)
    log.info("=" * 46)

    if not re.match(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$", config.BOT_TOKEN or ""):
        log.critical("BOT_TOKEN in config.py is missing or malformed.")
        sys.exit(1)

    db.init_db()
    os.makedirs(config.PROJECTS_DIR, exist_ok=True)
    os.makedirs(config.ZIPS_DIR, exist_ok=True)
    zip_builder.cleanup_old_zips()

    me = None
    for attempt in range(1, 6):
        try:
            me = bot.get_me()
            break
        except ApiTelegramException as error:
            if getattr(error, "error_code", None) == 401:
                log.critical("Telegram rejected BOT_TOKEN (401 Unauthorized). Check config.py.")
                sys.exit(1)
            log.error("Telegram API error (try %s/5): %s", attempt, error)
        except Exception as error:
            log.error("Cannot reach Telegram (try %s/5): %s", attempt, error)
        time.sleep(5)

    if me is None:
        log.critical("Could not connect to Telegram. Check the hosting network / token.")
        sys.exit(1)

    log.info("Connected as @%s", me.username)

    try:
        bot.remove_webhook()
    except Exception as error:
        log.warning("remove_webhook failed: %s", error)

    gemini_ok, gemini_message = ai_client.check_model()
    (log.info if gemini_ok else log.warning)(gemini_message)

    try:
        bot.set_my_commands([
            types.BotCommand("start", "القائمة الرئيسية"),
            types.BotCommand("new", "إنشاء مشروع جديد"),
            types.BotCommand("projects", "مشاريعي"),
            types.BotCommand("account", "حسابي"),
            types.BotCommand("hosting", "الاستضافة"),
            types.BotCommand("developer", "المطور"),
            types.BotCommand("help", "المساعدة"),
            types.BotCommand("cancel", "إلغاء العملية الحالية"),
        ])
    except Exception as error:
        log.warning("set_my_commands failed: %s", error)

    notify_admin(
        f"✅ <b>{esc(config.BOT_NAME)} v{config.BOT_VERSION} يعمل الآن</b>\n"
        f"🤖 @{esc(me.username)}\n"
        f"{'🧠 ' if gemini_ok else '⚠️ '}{esc(gemini_message)}\n"
        f"💾 <code>{esc(config.DATA_DIR)}</code>"
    )

    log.info("Bot is running...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True,
                         allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

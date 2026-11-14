# -*- coding: utf-8 -*-
# ==========================================================
#  DARK ELGENERAL — Admin Panel (reply-keyboard)
#  Subscribers • Stats • Broadcast • Forward • Forced
#  subscription • Maintenance • Notifications • Ban / Unban
# ----------------------------------------------------------
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================
#  Opened ONLY with the /admin command (also /rembo).
#  Users, bans and settings are stored in the bot's SQLite DB.
# ==========================================================

import threading
import time

from telebot.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import database as db
from utils import esc, log

MEMBER_STATUSES = ("member", "administrator", "creator")


class AdminPanel(object):

    def __init__(self, bot, admin_id, extra_stats=None, on_back=None):
        self.bot = bot
        self.admin_id = admin_id
        self.extra_stats = extra_stats       # callable -> HTML text appended to the stats
        self.on_back = on_back               # callable(chat_id) after "⬅️ رجوع"
        self.admin_state = {}                # admin_id -> "ban" | "unban" | ...
        self._register_handlers()

    # ---------- settings (stored in the database) ----------
    def is_admin(self, user_id):
        return user_id == self.admin_id

    def is_maintenance(self):
        return bool(db.get_kv("maintenance", False))

    def set_maintenance(self, enabled):
        db.set_kv("maintenance", bool(enabled))

    def is_notify_enabled(self):
        return bool(db.get_kv("notify_new_users", True))

    def get_channel_username(self):
        return db.get_kv("channel_username", None)

    def get_channel_link(self):
        return db.get_kv("channel_link", None)

    def clear_state(self, user_id):
        self.admin_state.pop(user_id, None)

    # ---------- forced subscription ----------
    @staticmethod
    def _chat_ref(channel):
        return int(channel) if str(channel).lstrip("-").isdigit() else channel

    def is_subscribed(self, user_id):
        """True / False, or None when it cannot be verified (bot not admin, bad ID...)."""
        channel = self.get_channel_username()
        if not channel:
            return True
        try:
            member = self.bot.get_chat_member(self._chat_ref(channel), user_id)
            return member.status in MEMBER_STATUSES or (
                member.status == "restricted" and bool(getattr(member, "is_member", False))
            )
        except Exception as error:
            log.warning("subscription check failed for %s: %s", channel, error)
            return None

    # ---------- keyboard ----------
    def panel_keyboard(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        status_btn = "🔓 فتح البوت" if self.is_maintenance() else "🔒 إغلاق البوت (صيانة)"
        notify_btn = "🔕 تعطيل التنبيه" if self.is_notify_enabled() else "🔔 تفعيل التنبيه"

        keyboard.add(KeyboardButton("👥 عدد المشتركين"), KeyboardButton("📊 إحصائيات"))
        keyboard.add(KeyboardButton("📢 إذاعة رسالة"), KeyboardButton("🔄 توجيه رسالة"))
        keyboard.add(KeyboardButton("💢 وضع اشتراك إجباري"), KeyboardButton("🗑 حذف اشتراك إجباري"))
        keyboard.add(KeyboardButton(notify_btn))
        keyboard.add(KeyboardButton(status_btn))
        keyboard.add(KeyboardButton("🚫 حظر عضو"), KeyboardButton("✅ إلغاء حظر عضو"))
        keyboard.add(KeyboardButton("⬅️ رجوع"))
        return keyboard

    def open(self, chat_id):
        self.bot.send_message(
            chat_id,
            "⚙️ <b>لوحة تحكم الأدمن</b>\n\nاهلا بيك عزيزي، إليك أوامرك ⚡📮",
            reply_markup=self.panel_keyboard(),
        )

    # ---------- broadcast / forward (own thread) ----------
    def _deliver(self, admin_chat, message, mode):
        success = fail = 0
        for user_id in db.all_user_ids():
            try:
                if mode == "forward":
                    self.bot.forward_message(user_id, message.chat.id, message.message_id)
                else:
                    # copy_message keeps text, formatting and every media type
                    self.bot.copy_message(user_id, message.chat.id, message.message_id)
                success += 1
            except Exception:
                fail += 1
            time.sleep(0.05)

        title = "✅ تم التوجيه" if mode == "forward" else "✅ انتهت الإذاعة"
        self.bot.send_message(admin_chat, f"{title}\nناجح: {success}\nفشل: {fail}")

    # ---------- handlers ----------
    def _register_handlers(self):
        bot = self.bot

        def admin_text(options):
            options = [options] if isinstance(options, str) else list(options)
            return lambda m: (m.text in options) and self.is_admin(m.from_user.id)

        @bot.message_handler(commands=["admin", "rembo"])
        def open_panel(message):
            if not self.is_admin(message.from_user.id):
                return
            self.clear_state(message.from_user.id)
            self.open(message.chat.id)

        @bot.message_handler(func=admin_text("⬅️ رجوع"))
        def back(message):
            self.clear_state(message.from_user.id)
            bot.send_message(message.chat.id, "تم الرجوع.", reply_markup=ReplyKeyboardRemove())
            if self.on_back:
                self.on_back(message.chat.id)

        @bot.message_handler(func=admin_text("👥 عدد المشتركين"))
        def members_count(message):
            bot.reply_to(message, f"👥 عدد المشتركين: <b>{db.count_users()}</b>")

        @bot.message_handler(func=admin_text("📊 إحصائيات"))
        def stats(message):
            maintenance = "مفعل 🔒" if self.is_maintenance() else "معطل 🔓"
            notify = "مفعل 🔔" if self.is_notify_enabled() else "معطل 🔕"
            channel = esc(self.get_channel_username() or "غير محددة")
            text = (
                "📊 <b>إحصائيات البوت</b>\n\n"
                f"👥 عدد المستخدمين: <b>{db.count_users()}</b>\n"
                f"🚫 المحظورين: <b>{db.count_banned()}</b>\n"
                f"🛠 حالة الصيانة: <b>{maintenance}</b>\n"
                f"🔔 التنبيه: <b>{notify}</b>\n"
                f"📢 القناة الإجبارية: <code>{channel}</code>"
            )
            if self.extra_stats:
                try:
                    text += "\n\n" + self.extra_stats()
                except Exception:
                    log.exception("extra stats failed")
            bot.reply_to(message, text)

        @bot.message_handler(func=admin_text(["🔒 إغلاق البوت (صيانة)", "🔓 فتح البوت"]))
        def toggle_maintenance(message):
            current = self.is_maintenance()
            self.set_maintenance(not current)
            bot.reply_to(
                message,
                "🔓 تم فتح البوت." if current else "🔒 تم إغلاق البوت.",
                reply_markup=self.panel_keyboard(),
            )

        @bot.message_handler(func=admin_text(["🔔 تفعيل التنبيه", "🔕 تعطيل التنبيه"]))
        def toggle_notify(message):
            current = self.is_notify_enabled()
            db.set_kv("notify_new_users", not current)
            bot.reply_to(
                message,
                "✅ تم تعطيل التنبيه." if current else "✅ تم تفعيل التنبيه.",
                reply_markup=self.panel_keyboard(),
            )

        def prompt(state, text):
            def handler(message):
                self.admin_state[message.from_user.id] = state
                bot.reply_to(message, text)
            return handler

        bot.message_handler(func=admin_text("🚫 حظر عضو"))(
            prompt("ban", "أرسل آي دي المستخدم اللي عايز تحظره:"))
        bot.message_handler(func=admin_text("✅ إلغاء حظر عضو"))(
            prompt("unban", "أرسل آي دي المستخدم اللي عايز تفك عنه الحظر:"))
        bot.message_handler(func=admin_text("📢 إذاعة رسالة"))(
            prompt("broadcast", "أرسل الرسالة اللي عايز تبعتها لكل المستخدمين:"))
        bot.message_handler(func=admin_text("🔄 توجيه رسالة"))(
            prompt("forward", "قم بتوجيه الرسالة اللي عايز تبعتها لكل المستخدمين:"))

        @bot.message_handler(func=admin_text("💢 وضع اشتراك إجباري"))
        def set_channel_prompt(message):
            self.admin_state[message.from_user.id] = "set_channel"
            bot.reply_to(
                message,
                "أرسل معرف القناة أو الـ ID:\nمثال: <code>@channel_name</code>\n\n"
                "⚠️ لازم تضيف البوت <b>أدمن</b> في القناة.",
            )

        @bot.message_handler(func=admin_text("🗑 حذف اشتراك إجباري"))
        def delete_channel(message):
            db.set_kv("channel_username", None)
            db.set_kv("channel_link", None)
            bot.reply_to(message, "✅ تم حذف القناة الإجبارية.", reply_markup=self.panel_keyboard())

        @bot.message_handler(
            func=lambda m: self.is_admin(m.from_user.id)
            and m.from_user.id in self.admin_state
            and not (m.text or "").startswith("/"),
            content_types=["text", "photo", "document", "audio", "voice", "video"],
        )
        def admin_actions(message):
            admin = message.from_user.id
            state = self.admin_state.get(admin)
            if not state:
                return
            text = (message.text or "").strip()

            if state in ("ban", "unban"):
                if not text.lstrip("-").isdigit():
                    bot.reply_to(message, "❌ آي دي غير صحيح.")
                    return
                user_id = int(text)
                self.clear_state(admin)

                if state == "ban":
                    if user_id == self.admin_id:
                        bot.reply_to(message, "❌ مش هتقدر تحظر نفسك.")
                        return
                    db.set_banned(user_id, True)
                    bot.reply_to(message, f"✅ تم حظر المستخدم <code>{user_id}</code>")
                    notice = "تم حظرك من قبل المطور 😒"
                else:
                    db.set_banned(user_id, False)
                    bot.reply_to(message, f"✅ تم فك الحظر عن <code>{user_id}</code>")
                    notice = "تم إلغاء حظرك من البوت 🤩"
                try:
                    bot.send_message(user_id, notice)
                except Exception:
                    pass

            elif state in ("broadcast", "forward"):
                self.clear_state(admin)
                bot.reply_to(
                    message,
                    f"⏳ جاري {'التوجيه' if state == 'forward' else 'الإذاعة'} "
                    f"لـ {len(db.all_user_ids())} مستخدم...",
                )
                threading.Thread(
                    target=self._deliver, args=(message.chat.id, message, state), daemon=True
                ).start()

            elif state == "set_channel":
                if text.startswith("@") and len(text) > 2:
                    link = f"https://t.me/{text[1:]}"
                elif text.lstrip("-").isdigit():
                    link = f"https://t.me/c/{text.replace('-100', '', 1)}"
                else:
                    bot.reply_to(message, "❌ صيغة غير صحيحة. أرسل @username أو الـ ID.")
                    return

                db.set_kv("channel_username", text)
                db.set_kv("channel_link", link)
                self.clear_state(admin)

                warning = ""
                try:
                    status = bot.get_chat_member(self._chat_ref(text), bot.get_me().id).status
                    if status not in ("administrator", "creator"):
                        warning = "\n\n⚠️ البوت مش أدمن في القناة، أضفه كأدمن عشان يتحقق من الاشتراك."
                except Exception:
                    warning = "\n\n⚠️ تعذّر الوصول للقناة. تأكد من المعرف وأن البوت أدمن فيها."

                bot.reply_to(
                    message,
                    f"✅ تم وضع الاشتراك الإجباري.\nالقناة: <code>{esc(text)}</code>{warning}",
                    reply_markup=self.panel_keyboard(),
                )


def setup_admin(bot, admin_id, extra_stats=None, on_back=None):
    """Activate the panel. Call it BEFORE registering the bot's other handlers."""
    return AdminPanel(bot, admin_id, extra_stats=extra_stats, on_back=on_back)

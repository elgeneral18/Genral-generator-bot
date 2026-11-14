# ==========================================================
#  DARK ELGENERAL — Utilities
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import html
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

import config


# ----------------------------------------------------------
#  LOGGING  (console + bot.log)
# ----------------------------------------------------------

log = logging.getLogger("dark_elgeneral")


def setup_logging():
    if log.handlers:
        return log

    log.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    log.addHandler(console)

    try:
        file_handler = RotatingFileHandler(
            config.LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)
    except OSError:
        pass

    # Show telebot's own errors (409 conflict, network problems...) in our log
    telebot_logger = logging.getLogger("TeleBot")
    telebot_logger.setLevel(logging.INFO)
    for handler in log.handlers:
        telebot_logger.addHandler(handler)

    return log


# ----------------------------------------------------------
#  TEXT HELPERS
# ----------------------------------------------------------

def esc(value):
    """Escape text for Telegram HTML."""
    return html.escape(str(value), quote=False)


def short(text, limit=80):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def slugify(text, default="project"):
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text or "")).strip("-._")
    return text[:60] or default


def human_size(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def bar(percent, width=10):
    percent = max(0, min(100, int(percent)))
    filled = round(width * percent / 100)
    return "▰" * filled + "▱" * (width - filled)


# ----------------------------------------------------------
#  TIME  (daily reset follows the configured local offset)
# ----------------------------------------------------------

def local_now():
    tz = timezone(timedelta(hours=config.LOCAL_UTC_OFFSET_HOURS))
    return datetime.now(tz)


def now_str():
    return local_now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return local_now().strftime("%Y-%m-%d")


def pretty_date(value):
    """'2026-11-14 10:30:00' -> '14/11/2026'"""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(value or "-")

# ==========================================================
#  DARK ELGENERAL  —  AI Project Generator Bot
#  Configuration TEMPLATE — copy to config.py and fill in your values
# ==========================================================
#  © 2026 Dark Elgeneral — Developed by Adam Elgeneral
# ==========================================================

import os
import tempfile


# ----------------------------------------------------------
#  SECRETS  (private use)
# ----------------------------------------------------------
BOT_TOKEN = "123456789:PUT_YOUR_BOT_TOKEN_HERE"

GEMINI_API_KEY = "PUT_YOUR_GEMINI_API_KEY_HERE"
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_MAX_OUTPUT_TOKENS = 65536


# ----------------------------------------------------------
#  ADMIN
# ----------------------------------------------------------
ADMIN_ID = 123456789
ADMIN_NOTIFICATIONS = True          # new users / new projects / errors


# ----------------------------------------------------------
#  BRAND & COPYRIGHT
# ----------------------------------------------------------
BOT_NAME = "Dark Elgeneral"
BOT_VERSION = "2.2.0"
DEVELOPER_NAME = "Adam Elgeneral"
COPYRIGHT = "© 2026 Dark Elgeneral • Developed by Adam Elgeneral"
ADD_CREDIT_FILE = True              # adds GENERATED_BY.txt inside every ZIP


# ----------------------------------------------------------
#  CONTACT & HOSTING LINKS
# ----------------------------------------------------------
CONTACT_TELEGRAM = "Dark_E7x"
CONTACT_WHATSAPP = "201507119434"   # +20 15 07119434
BOT_HOSTING_URL = "https://t.me/D_A_M_ABOT"
WEB_HOSTING_URL = "https://vercel.com"


# ----------------------------------------------------------
#  LIMITS
# ----------------------------------------------------------
DAILY_LIMIT = 5                     # projects per user per day (admin = unlimited)
COOLDOWN_SECONDS = 60               # wait time between two generations
MAX_CONCURRENT_GENERATIONS = 3      # extra requests wait in a queue
MAX_IMAGES_PER_PROJECT = 10
MAX_IMAGE_MB = 10
LOCAL_UTC_OFFSET_HOURS = 2          # used for the daily reset (Egypt)


# ----------------------------------------------------------
#  STORAGE  (always relative to this file, never to the cwd)
# ----------------------------------------------------------
DATABASE_NAME = "dark_elgeneral.db"
PROJECTS_FOLDER = "projects"
ZIPS_FOLDER = "zips"
LOG_FILE = "bot.log"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _pick_data_dir():
    """Use the bot folder; fall back to the temp dir if it is read-only."""
    for candidate in (BASE_DIR, os.path.join(tempfile.gettempdir(), "dark_elgeneral")):
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".write_test")
            with open(probe, "w") as handle:
                handle.write("ok")
            os.remove(probe)
            return candidate
        except OSError:
            continue
    return BASE_DIR


DATA_DIR = _pick_data_dir()
DATABASE_PATH = os.path.join(DATA_DIR, DATABASE_NAME)
PROJECTS_DIR = os.path.join(DATA_DIR, PROJECTS_FOLDER)
ZIPS_DIR = os.path.join(DATA_DIR, ZIPS_FOLDER)
LOG_PATH = os.path.join(DATA_DIR, LOG_FILE)

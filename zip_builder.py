# ==========================================================
#  DARK ELGENERAL — ZIP builder
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import os
import time
import uuid
import zipfile

import config
import catalog
from utils import slugify

SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def cleanup_old_zips(max_age_seconds=3600):
    """Delete leftover ZIPs (e.g. after a crash)."""
    try:
        for name in os.listdir(config.ZIPS_DIR):
            path = os.path.join(config.ZIPS_DIR, name)
            if name.endswith(".zip") and time.time() - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
    except OSError:
        pass


def build_zip(project_dir, project_name, project_type):
    """Zip the project folder. Returns the ZIP path."""
    os.makedirs(config.ZIPS_DIR, exist_ok=True)
    cleanup_old_zips()

    slug = slugify(project_name)
    zip_path = os.path.join(config.ZIPS_DIR, f"{slug}-{uuid.uuid4().hex[:6]}.zip")
    added = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder, dirs, names in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                full = os.path.join(folder, name)
                relative = os.path.relpath(full, project_dir)
                archive.write(full, os.path.join(slug, relative))
                added += 1

        archive.writestr(
            os.path.join(slug, "HOSTING_GUIDE.md"),
            catalog.hosting_guide_markdown(project_type, slug),
        )
        if config.ADD_CREDIT_FILE:
            archive.writestr(
                os.path.join(slug, "GENERATED_BY.txt"),
                catalog.credit_text(project_type, slug),
            )

    if added == 0:
        os.remove(zip_path)
        raise ValueError("Project folder is empty.")

    return zip_path

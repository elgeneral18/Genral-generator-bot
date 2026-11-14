# ==========================================================
#  DARK ELGENERAL — Safe project file writer / reader
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import os

from utils import log

MAX_FILES = 120
MAX_FILE_BYTES = 800_000

TEXT_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt",
    ".py", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".example", ".xml", ".svg",
    ".sql", ".csv", ".sh", ".gitignore",
}


def _safe_relative(path):
    """Return a safe relative path or None."""
    path = (path or "").replace("\\", "/").strip().lstrip("/")
    normalized = os.path.normpath(path).replace("\\", "/")

    if not normalized or normalized in (".", "..") or os.path.isabs(normalized):
        return None
    if normalized.startswith("../") or "/../" in normalized:
        return None
    if "__pycache__" in normalized.split("/"):
        return None
    return normalized


def write_files(project_dir, files, delete=None):
    """Write generated files. A bad path or file never aborts the others."""
    os.makedirs(project_dir, exist_ok=True)
    root = os.path.realpath(project_dir)
    written = []

    for item in files[:MAX_FILES]:
        relative = _safe_relative(item["path"])
        if not relative:
            log.warning("WRITE SKIP (unsafe path): %s", item["path"])
            continue

        content = item["content"]
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            log.warning("WRITE SKIP (too large): %s", relative)
            continue

        full = os.path.realpath(os.path.join(root, relative))
        if not full.startswith(root + os.sep):
            continue

        # Never overwrite images uploaded by the user
        if relative.startswith("images/") and os.path.exists(full):
            continue

        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            written.append(relative)
        except OSError as error:
            log.warning("WRITE SKIP %s: %s", relative, error)

    for path in delete or []:
        relative = _safe_relative(path)
        if not relative or relative.startswith("images/"):
            continue
        full = os.path.realpath(os.path.join(root, relative))
        if full.startswith(root + os.sep) and os.path.isfile(full):
            try:
                os.remove(full)
            except OSError:
                pass

    return written


def count_files(project_dir):
    total = 0
    for _, _, names in os.walk(project_dir):
        total += len(names)
    return total


def read_project_files(project_dir, max_total=250_000):
    """Return [(relative_path, text)] of the project's text files (for AI edits)."""
    collected, total = [], 0

    for folder, dirs, names in os.walk(project_dir):
        dirs[:] = sorted(d for d in dirs if d not in ("images", "assets", "__pycache__", ".git"))
        for name in sorted(names):
            full = os.path.join(folder, name)
            extension = os.path.splitext(name)[1].lower()
            if extension not in TEXT_EXTENSIONS and name not in (".gitignore", ".env.example"):
                continue
            try:
                if os.path.getsize(full) > 120_000:
                    continue
                with open(full, "r", encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeDecodeError):
                continue

            total += len(text)
            if total > max_total:
                return collected
            collected.append((os.path.relpath(full, project_dir).replace("\\", "/"), text))

    return collected


def add_credit_header(path, header):
    """Insert the copyright header at the top of a .py file (idempotent)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        return False

    if "Dark Elgeneral" in text[:600]:
        return False

    lines = text.split("\n")
    index = 0
    # keep shebang / encoding lines first
    while index < len(lines) and index < 2 and (
        lines[index].startswith("#!") or "coding" in lines[index][:30]
    ):
        index += 1

    lines[index:index] = header.rstrip("\n").split("\n") + [""]
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines))
        return True
    except OSError:
        return False

# ==========================================================
#  DARK ELGENERAL — Prompt builder & response parser
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import json
import re

from utils import slugify

SYSTEM_PROMPT = """
You are a senior software engineer and product designer working for "Dark Elgeneral".
Convert the user's idea into a complete, production-quality, well-structured project.

GENERAL RULES:
1. Understand the idea first, then design the file structure.
2. Every file is returned separately with its full content - never merge files.
3. Code must be clean, commented only where useful, and ready to run without edits
   (except placeholders for secrets such as tokens/API keys).
4. Write real, meaningful content - never lorem ipsum or "TODO" placeholders.
5. Never invent image filenames. Use only the images that are explicitly provided.
6. Include a README.md with clear setup and run instructions (except when the
   project type says it must be a single file).
7. Return valid JSON only. No markdown fences, no text outside the JSON.
"""

TYPE_PROMPTS = {
    "website": """
The project is a WEBSITE (static frontend, deployable on Vercel).
- Files: index.html at the project root + css/ + js/ (+ extra pages when useful).
- Premium modern design: CSS variables, consistent spacing, great typography,
  smooth scroll/hover/reveal animations, glassmorphism or gradients where fitting.
- Fully responsive (mobile first), semantic HTML, accessibility, SEO meta tags,
  Open Graph tags and an inline SVG favicon.
- No build tools required. Plain HTML/CSS/JavaScript unless the user asks otherwise.
- Use Google Fonts when appropriate (Cairo or Tajawal for Arabic text).
""",
    "telegram_bot": """
The project is a TELEGRAM BOT.
- Python with pyTelegramBotAPI (telebot) unless the user asks otherwise.
- Files: main.py, config.py (placeholders for BOT_TOKEN and ADMIN_ID), requirements.txt,
  database module (SQLite) when storage is needed, handlers split logically.
- Use inline keyboards, clear Arabic/English messages (as the user prefers),
  input validation, error handling and logging.
- Bots must never crash on bad input; wrap risky code and keep polling alive.
""",
    "discord_bot": """
The project is a DISCORD BOT.
- Python with discord.py (2.x) using slash commands (app_commands) and buttons/views.
- Files: main.py, config.py (placeholder for TOKEN), requirements.txt,
  cogs/ for feature modules, database module (SQLite) when storage is needed.
- Include the required intents, permission checks and friendly embeds.
""",
    "python_tool": """
The project is a PYTHON TOOL delivered as ONE SINGLE FILE.
- Return EXACTLY ONE file: a self-contained Python 3 script (for example "tool.py").
- Put ALL the code in that one file. No README, no requirements.txt, no extra files.
- Prefer the standard library. If third-party packages are really needed, list them in a
  short comment block at the top (e.g. "# pip install requests") and import them normally.
- Clean CLI with argparse (--help), a main() function and the if __name__ == "__main__" guard,
  logging, clear error messages and a module docstring that explains usage with examples.
- Only legitimate, lawful functionality. Respect robots.txt and rate limits when fetching web data.
""",
}

THEMES = {
    "dark": "dark theme (deep dark background, neon/gradient accents)",
    "light": "light theme (clean bright background, soft shadows)",
    "glass": "glassmorphism style (blurred translucent cards over a vivid gradient background)",
}

RETURN_FORMAT_NEW = """
RETURN ONLY valid JSON in exactly this structure:
{
  "project_name": "short-ascii-slug",
  "description": "one short sentence",
  "files": [
    {"path": "index.html", "content": "full file content"},
    {"path": "css/style.css", "content": "full file content"}
  ]
}
"""

RETURN_FORMAT_MODIFY = """
RETURN ONLY valid JSON in exactly this structure:
{
  "description": "one short sentence describing what changed",
  "files": [
    {"path": "index.html", "content": "FULL new content of every changed or new file"}
  ],
  "delete": ["paths/of/files/to/remove"]
}
Return the COMPLETE content of every file you change (never diffs or fragments).
Do NOT return files that did not change.
"""


def _options_text(project_type, options):
    options = options or {}
    lines = []

    if project_type == "website":
        lines.append("- Design style: " + THEMES.get(options.get("theme"), THEMES["dark"]))
        if options.get("site_lang") == "en":
            lines.append("- Website language: English (LTR)")
        else:
            lines.append('- Website language: Arabic, with dir="rtl" and lang="ar"')
    else:
        if options.get("site_lang") == "en":
            lines.append("- Messages / UI text language: English")
        else:
            lines.append("- Messages / UI text language: Arabic")

    return "\n".join(lines)


def _images_text(images):
    if not images:
        return "No images were provided."

    lines = []
    for image in images:
        line = f"- images/{image['name']}"
        if image.get("desc"):
            line += f"   (user note: {image['desc']})"
        lines.append(line)
    return "\n".join(lines) + (
        "\nThe images are stored in the images/ folder. Reference them with these exact paths."
    )


def build_prompt(project_type, idea, images=None, options=None):
    return f"""{SYSTEM_PROMPT}

PROJECT TYPE: {project_type}
{TYPE_PROMPTS.get(project_type, "")}

PREFERENCES:
{_options_text(project_type, options)}

USER IDEA:
{idea}

PROVIDED IMAGES:
{_images_text(images)}

{RETURN_FORMAT_NEW}"""


def build_modify_prompt(project_type, existing_files, request, images=None, options=None):
    files_text = "\n\n".join(
        f"=== FILE: {path} ===\n{content}" for path, content in existing_files
    )
    return f"""{SYSTEM_PROMPT}

You are MODIFYING an existing {project_type} project. Apply the requested changes,
keep everything else working, and keep the existing code style.

PREFERENCES:
{_options_text(project_type, options)}

EXISTING PROJECT FILES:
{files_text}

PROVIDED IMAGES:
{_images_text(images)}

REQUESTED CHANGES:
{request}

{RETURN_FORMAT_MODIFY}"""


# ----------------------------------------------------------
#  RESPONSE PARSING
# ----------------------------------------------------------

def clean_json_text(response):
    text = (response or "").strip()

    # Remove a wrapping markdown fence ONLY. Never search for fences inside the
    # text: generated README.md files contain ``` inside JSON strings.
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]

    return text


def salvage_files(text):
    """Recover complete file objects from a truncated JSON response."""
    match = re.search(r'"files"\s*:\s*\[', text)
    if not match:
        return []

    decoder = json.JSONDecoder(strict=False)
    position, files = match.end(), []

    while position < len(text):
        while position < len(text) and text[position] in " \r\n\t,":
            position += 1
        if position >= len(text) or text[position] != "{":
            break
        try:
            item, position = decoder.raw_decode(text, position)
        except ValueError:
            break
        files.append(item)

    return files


def _valid_files(items):
    files = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        path, content = item.get("path"), item.get("content")
        if isinstance(path, str) and path.strip() and isinstance(content, str):
            files.append({"path": path.strip(), "content": content})
    return files


def parse_response(response_text, require_name=True):
    cleaned = clean_json_text(response_text)
    truncated = False

    try:
        data = json.loads(cleaned, strict=False)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        items = data.get("files")
    except ValueError:
        items = salvage_files(cleaned)
        if not items:
            return {"success": False, "error": "AI response is not valid JSON."}
        truncated = True
        name_match = re.search(r'"project_name"\s*:\s*"([^"]+)"', cleaned)
        data = {"project_name": name_match.group(1) if name_match else "project"}

    files = _valid_files(items)
    if not files:
        return {"success": False, "error": "AI response contains no files."}

    deletions = [p for p in (data.get("delete") or []) if isinstance(p, str)]

    return {
        "success": True,
        "project_name": slugify(data.get("project_name") or "project"),
        "description": str(data.get("description") or "")[:300],
        "files": files,
        "delete": deletions,
        "truncated": truncated,
    }

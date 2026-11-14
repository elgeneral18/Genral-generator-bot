# ==========================================================
#  DARK ELGENERAL — In-memory user sessions
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================
#  Steps:  idea -> images -> generating -> (failed | done)
#          request (modify an existing project) -> generating
# ==========================================================

import os
import shutil
import threading
import uuid

import config

_lock = threading.RLock()
_sessions = {}


def _discard(session):
    """Remove the half-created folder of a project that was never saved."""
    if session.get("mode") == "new" and not session.get("saved"):
        shutil.rmtree(session.get("project_dir", ""), ignore_errors=True)


def start(user_id, project_type, mode="new", project=None):
    with _lock:
        old = _sessions.pop(user_id, None)
    if old and not old.get("busy"):
        _discard(old)

    if mode == "modify" and project:
        project_id = project["project_id"]
        project_dir = project["path"]
        step = "request"
    else:
        project_id = uuid.uuid4().hex[:8]
        project_dir = os.path.join(config.PROJECTS_DIR, str(user_id), project_id)
        step = "idea"

    session = {
        "mode": mode,
        "type": project_type,
        "step": step,
        "idea": "",
        "images": [],            # [{"name": ..., "desc": ...}]
        "project_id": project_id,
        "project_dir": project_dir,
        "images_dir": os.path.join(project_dir, "images"),
        "busy": False,
        "saved": mode == "modify",
    }
    with _lock:
        _sessions[user_id] = session
    return session


def get(user_id):
    with _lock:
        return _sessions.get(user_id)


def set_step(user_id, step):
    with _lock:
        session = _sessions.get(user_id)
        if session:
            session["step"] = step
        return bool(session)


def transition(user_id, from_steps, to_step):
    """Atomically move a session between steps (guards against double clicks)."""
    with _lock:
        session = _sessions.get(user_id)
        if not session or session["step"] not in from_steps:
            return False
        session["step"] = to_step
        return True


def clear(user_id, force=False):
    with _lock:
        session = _sessions.get(user_id)
        if not session:
            return False
        if session.get("busy") and not force:
            return False
        _sessions.pop(user_id, None)
    _discard(session)
    return True

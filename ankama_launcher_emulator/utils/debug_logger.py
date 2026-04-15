"""Debug request/response logger for HAAPI traffic.

Enable by setting env var ANKAMA_DEBUG_HAAPI=1 or creating a file
named 'debug_haapi' in the app config directory.

Logs are written to app_config_dir/haapi_debug.log as JSON lines.
"""

import json
import logging
import os
from datetime import datetime

import requests

from ankama_launcher_emulator.consts import app_config_dir

logger = logging.getLogger()

DEBUG_LOG_PATH = os.path.join(app_config_dir, "haapi_debug.log")
DEBUG_FLAG_FILE = os.path.join(app_config_dir, "debug_haapi")


def is_debug_enabled() -> bool:
    return os.environ.get("ANKAMA_DEBUG_HAAPI") == "1" or os.path.exists(
        DEBUG_FLAG_FILE
    )


def toggle_debug() -> bool:
    """Toggle debug mode. Returns new state."""
    if os.path.exists(DEBUG_FLAG_FILE):
        os.remove(DEBUG_FLAG_FILE)
        logger.info("[DEBUG] HAAPI debug logging disabled")
        return False
    else:
        with open(DEBUG_FLAG_FILE, "w") as f:
            f.write("1")
        logger.info(f"[DEBUG] HAAPI debug logging enabled → {DEBUG_LOG_PATH}")
        return True


def _log_entry(entry: dict) -> None:
    try:
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as err:
        logger.warning(f"[DEBUG] Failed to write debug log: {err}")


def hook_session(session: requests.Session) -> None:
    """Attach response hook to session for debug logging."""
    if not is_debug_enabled():
        return

    def _log_response(response: requests.Response, *args, **kwargs):
        req = response.request
        req_body = None
        if req.body:
            if isinstance(req.body, bytes):
                try:
                    req_body = req.body.decode("utf-8", errors="replace")
                except Exception:
                    req_body = f"<{len(req.body)} bytes>"
            else:
                req_body = str(req.body)

        resp_body = None
        if response.content:
            try:
                resp_body = response.json()
            except (ValueError, UnicodeDecodeError):
                resp_body = response.text[:2000]

        entry = {
            "timestamp": datetime.now().isoformat(),
            "request": {
                "method": req.method,
                "url": req.url,
                "headers": dict(req.headers),
                "body": req_body,
            },
            "response": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": resp_body,
            },
        }
        _log_entry(entry)

    session.hooks["response"].append(_log_response)

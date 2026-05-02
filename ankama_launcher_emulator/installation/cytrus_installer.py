import logging
import os
import shutil
import subprocess
from typing import Callable

from ankama_launcher_emulator.consts import (
    _get_local_cytrus_dir,
    ensure_cytrus_in_path,
    is_cytrus_installed,
)
from ankama_launcher_emulator.installation.node_manager import ensure_node, get_npm_path

logger = logging.getLogger()


def install_cytrus(
    on_progress: Callable[[str], None] | None = None,
) -> bool:
    """Install cytrus-v6 locally using portable Node.js.

    Returns True on success, False otherwise.
    """
    if is_cytrus_installed():
        return True

    if on_progress:
        on_progress("Installing Node.js...")

    node_dir = ensure_node(on_progress=on_progress)
    if node_dir is None:
        if on_progress:
            on_progress("Failed to install Node.js")
        logger.error("[CYTRUS_INSTALL] Node.js installation failed")
        return False

    npm = get_npm_path()
    if npm is None:
        if on_progress:
            on_progress("npm not found after Node.js install")
        logger.error("[CYTRUS_INSTALL] npm not found")
        return False

    local_cytrus = _get_local_cytrus_dir()
    os.makedirs(local_cytrus, exist_ok=True)

    if on_progress:
        on_progress("Installing cytrus-v6 (this may take a minute)...")

    try:
        result = subprocess.run(
            [
                npm,
                "install",
                "cytrus-v6",
                "--prefix",
                local_cytrus,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug("[CYTRUS_INSTALL] npm output: %s", result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error("[CYTRUS_INSTALL] npm install failed: %s", exc.stderr)
        if on_progress:
            on_progress("cytrus-v6 installation failed")
        return False
    except Exception as exc:
        logger.error("[CYTRUS_INSTALL] Unexpected error: %s", exc)
        if on_progress:
            on_progress("cytrus-v6 installation failed")
        return False

    # Update PATH so subprocess calls find cytrus-v6 immediately
    ensure_cytrus_in_path()

    if is_cytrus_installed():
        logger.info("[CYTRUS_INSTALL] cytrus-v6 installed successfully")
        if on_progress:
            on_progress("cytrus-v6 installed successfully")
        return True

    logger.error("[CYTRUS_INSTALL] cytrus-v6 not found after npm install")
    if on_progress:
        on_progress("cytrus-v6 installation failed")
    return False

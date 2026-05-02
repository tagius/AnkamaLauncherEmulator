import logging
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from typing import Callable

from ankama_launcher_emulator.consts import _get_local_node_dir

logger = logging.getLogger()

NODE_VERSION = "v22.14.0"
NODE_DOWNLOAD_URL = (
    f"https://nodejs.org/dist/{NODE_VERSION}/" f"node-{NODE_VERSION}-win-x64.zip"
)


def ensure_node(
    on_progress: Callable[[str], None] | None = None,
) -> str | None:
    """Download and extract portable Node.js if not already present.

    Returns the directory containing node.exe, or None on failure.
    """
    local_node = _get_local_node_dir()
    node_exe = os.path.join(local_node, "node.exe")

    if os.path.exists(node_exe):
        return local_node

    if on_progress:
        on_progress("Downloading Node.js...")

    try:
        os.makedirs(local_node, exist_ok=True)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name

        logger.info("[NODE] Downloading %s", NODE_DOWNLOAD_URL)
        urllib.request.urlretrieve(NODE_DOWNLOAD_URL, tmp_path)

        if on_progress:
            on_progress("Extracting Node.js...")

        extract_tmp = os.path.join(tempfile.gettempdir(), "node_extract")
        os.makedirs(extract_tmp, exist_ok=True)

        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(extract_tmp)

        # The zip contains a root folder like node-v22.14.0-win-x64/
        extracted_root = None
        for entry in os.listdir(extract_tmp):
            if entry.startswith("node-") and os.path.isdir(
                os.path.join(extract_tmp, entry)
            ):
                extracted_root = os.path.join(extract_tmp, entry)
                break

        if extracted_root is None:
            raise RuntimeError("Node.js zip did not contain expected root folder")

        # Move contents up to local_node
        for item in os.listdir(extracted_root):
            src = os.path.join(extracted_root, item)
            dst = os.path.join(local_node, item)
            if os.path.exists(dst):
                shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)
            shutil.move(src, dst)

        shutil.rmtree(extract_tmp)
        os.remove(tmp_path)

        if os.path.exists(node_exe):
            logger.info("[NODE] Portable Node.js installed at %s", local_node)
            return local_node

        raise RuntimeError("node.exe not found after extraction")

    except Exception as exc:
        logger.warning("[NODE] Failed to install portable Node.js: %s", exc)
        return None


def get_npm_path() -> str | None:
    """Return path to npm.cmd if local Node is installed."""
    local_node = _get_local_node_dir()
    npm = os.path.join(local_node, "npm.cmd")
    return npm if os.path.exists(npm) else None

"""AWS WAF token bypass for auth.ankama.com.

Ported from Bubble.D3 BubbleBot.Connect/AwsBypassService.cs.

Flow:
  1. GET challenge from AWS WAF token endpoint
  2. Generate random browser-fingerprint metrics JSON
  3. CRC32 checksum of metrics
  4. SHA256 proof-of-work: find i such that SHA256(input+checksum+str(i)) has N leading zero bits
  5. AES-256-GCM encrypt (checksum + "#" + metrics) with hardcoded key
  6. POST verify → {"token": "aws-waf-token..."}
"""

import base64
import binascii
import hashlib
import json
import logging
import os
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_CHALLENGE_URL = (
    "https://3f38f7f4f368.83dbb5dc.eu-south-1.token.awswaf.com"
    "/3f38f7f4f368/e1fcfc58118e/inputs?client=browser"
)
_VERIFY_URL = (
    "https://3f38f7f4f368.83dbb5dc.eu-south-1.token.awswaf.com"
    "/3f38f7f4f368/e1fcfc58118e/verify"
)

_CHALLENGE_TYPE_SHA256 = "h7b0c470f0cfe3a80a9e26526ad185f484f6817d0832712a4a37a908786a6a67f"

_AES_KEY = bytes.fromhex(
    "93d9f6846b629edb2bdc4466af627d998496cb0c08f9cf043de68d6b25aa9693"
)

_VERIFY_HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "text/plain;charset=UTF-8",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
}


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------


def _crc32_checksum(data: str) -> str:
    """CRC32 of UTF-8 bytes, uppercase hex 8 chars (matches C# CrcCalculator)."""
    value = binascii.crc32(data.encode("utf-8")) & 0xFFFFFFFF
    return f"{value:08X}"


def _satisfy_difficulty(difficulty: int, hash_bytes: bytes) -> bool:
    """True if hash_bytes has at least `difficulty` leading zero bits."""
    hash_int = int.from_bytes(hash_bytes, "big")
    return hash_int >> (256 - difficulty) == 0


def _solve_sha256(input_str: str, checksum: str, difficulty: int) -> str:
    """Find incrementor i such that SHA256(input+checksum+str(i)) satisfies difficulty."""
    prefix = (input_str + checksum).encode("utf-8")
    i = 0
    while True:
        data = prefix + str(i).encode("utf-8")
        h = hashlib.sha256(data).digest()
        if _satisfy_difficulty(difficulty, h):
            return str(i)
        i += 1


def _aes_gcm_encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt with hardcoded key.

    Returns '{b64(nonce)}::{hex(tag)}::{hex(ciphertext)}'.
    This is the Encrypt() output with 'KramerAndRio::' prefix stripped.
    """
    from Cryptodome.Cipher import AES  # pycryptodomex — already in deps

    nonce = os.urandom(12)
    cipher = AES.new(_AES_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
    return (
        f"{base64.b64encode(nonce).decode('ascii')}"
        f"::{tag.hex()}"
        f"::{ciphertext.hex()}"
    )


# ---------------------------------------------------------------------------
# Metrics generation
# ---------------------------------------------------------------------------


def _generate_metrics(state: str) -> tuple[str, dict[str, Any]]:
    """Generate random browser-fingerprint metrics JSON (port of C# GenerateMetrics).

    Returns (minified_json, metrics_obj).
    """
    f2p = random.randint(0, 1)
    browser = random.randint(0, 1)
    capabilities = random.randint(1, 2)
    dnt = random.randint(0, 1)
    gpu = random.randint(5, 20)
    be = random.randint(0, 2)
    canvas = random.randint(10, 200)

    timestamp1 = random.uniform(20, 60)
    timestamp2 = random.uniform(10, 30)

    now_ms = int(time.time() * 1000)
    start_ts = now_ms - 2
    end_ts = now_ms
    run_id = os.urandom(16).hex()

    location = (
        "https://auth.ankama.com/login/ankama/form"
        f"?origin_tracker=https://www.ankama-launcher.com/launcher"
        f"&redirect_uri=zaap://login&state={state}"
    )

    metrics_obj: dict[str, Any] = {
        "metrics": {
            "fp2": f2p,
            "browser": browser,
            "capabilities": capabilities,
            "gpu": gpu,
            "dnt": dnt,
            "math": 0,
            "screen": 0,
            "navigator": 0,
            "auto": 1,
            "stealth": 1,
            "subtle": 0,
            "canvas": canvas,
            "formdetector": 1,
            "be": be,
        },
        "start": start_ts,
        "flashVersion": None,
        "plugins": [
            {"name": "PDF Viewer", "str": "PDF Viewer "},
            {"name": "Chrome PDF Viewer", "str": "Chrome PDF Viewer "},
            {"name": "Chromium PDF Viewer", "str": "Chromium PDF Viewer "},
            {"name": "Microsoft Edge PDF Viewer", "str": "Microsoft Edge PDF Viewer "},
            {"name": "WebKit built-in PDF", "str": "WebKit built-in PDF "},
        ],
        "dupedPlugins": (
            "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer "
            "Microsoft Edge PDF Viewer WebKit built-in PDF ||1536-864-816-24-*-*-*"
        ),
        "screenInfo": "1536-864-816-24-*-*-*",
        "referrer": "",
        "userAgent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ),
        "location": location,
        "webDriver": False,
        "capabilities": {
            "css": {
                "textShadow": 1,
                "WebkitTextStroke": 1,
                "boxShadow": 1,
                "borderRadius": 1,
                "borderImage": 1,
                "opacity": 1,
                "transform": 1,
                "transition": 1,
            },
            "js": {
                "audio": True,
                "geolocation": True,
                "localStorage": "supported",
                "touch": False,
                "video": True,
                "webWorker": True,
            },
            "elapsed": 1,
        },
        "gpu": {
            "vendor": "Google Inc. (Intel)",
            "model": (
                "ANGLE (Intel, Intel(R) UHD Graphics (0x000046A3) "
                "Direct3D11 vs_5_0 ps_5_0, D3D11)"
            ),
            "extensions": [
                "ANGLE_instanced_arrays", "EXT_blend_minmax", "EXT_clip_control",
                "EXT_color_buffer_half_float", "EXT_depth_clamp",
                "EXT_disjoint_timer_query", "EXT_float_blend", "EXT_frag_depth",
                "EXT_polygon_offset_clamp", "EXT_shader_texture_lod",
                "EXT_texture_compression_bptc", "EXT_texture_compression_rgtc",
                "EXT_texture_filter_anisotropic", "EXT_texture_mirror_clamp_to_edge",
                "EXT_sRGB", "KHR_parallel_shader_compile", "OES_element_index_uint",
                "OES_fbo_render_mipmap", "OES_standard_derivatives",
                "OES_texture_float", "OES_texture_float_linear",
                "OES_texture_half_float", "OES_texture_half_float_linear",
                "OES_vertex_array_object", "WEBGL_blend_func_extended",
                "WEBGL_color_buffer_float", "WEBGL_compressed_texture_s3tc",
                "WEBGL_compressed_texture_s3tc_srgb", "WEBGL_debug_renderer_info",
                "WEBGL_debug_shaders", "WEBGL_depth_texture", "WEBGL_draw_buffers",
                "WEBGL_lose_context", "WEBGL_multi_draw", "WEBGL_polygon_mode",
            ],
        },
        "dnt": None,
        "math": {
            "tan": "-1.4214488238747245",
            "sin": "0.8178819121159085",
            "cos": "-0.5753861119575491",
        },
        "automation": {
            "wd": {"properties": {"document": [], "window": [], "navigator": []}},
            "phantom": {"properties": {"window": []}},
        },
        "stealth": {"t1": 0, "t2": 0, "i": 1, "mte": 0, "mtd": False},
        "crypto": {
            "crypto": 1, "subtle": 1, "encrypt": True, "decrypt": True,
            "wrapKey": True, "unwrapKey": True, "sign": True, "verify": True,
            "digest": True, "deriveBits": True, "deriveKey": True,
            "getRandomValues": True, "randomUUID": True,
        },
        "canvas": {
            "hash": -1191871006,
            "emailHash": None,
            "histogramBins": [
                14542, 25, 40, 33, 54, 45, 21, 39, 31, 44, 41, 29, 28, 28, 69, 55,
                17, 22, 76, 36, 27, 19, 18, 47, 40, 17, 24, 29, 63, 19, 45, 27, 38,
                18, 26, 14, 32, 19, 17, 32, 29, 43, 16, 50, 44, 17, 14, 46, 16, 21,
                16, 43, 14, 19, 7, 31, 24, 24, 19, 67, 31, 34, 15, 13, 20, 25, 37,
                15, 11, 19, 16, 20, 44, 20, 42, 16, 19, 7, 20, 55, 23, 16, 15, 31,
                21, 20, 31, 53, 19, 26, 19, 41, 15, 18, 10, 29, 46, 17, 37, 94, 53,
                35, 526, 46, 78, 39, 14, 13, 15, 20, 10, 21, 16, 17, 35, 21, 16, 12,
                28, 13, 25, 17, 24, 16, 30, 32, 63, 19, 24, 84, 22, 31, 36, 18, 20,
                19, 20, 47, 9, 16, 18, 19, 17, 17, 22, 33, 74, 23, 17, 9, 63, 11,
                12, 91, 11, 15, 29, 13, 24, 11, 11, 27, 10, 12, 53, 10, 6, 15, 27,
                52, 16, 13, 53, 17, 13, 13, 79, 10, 13, 11, 14, 15, 18, 85, 37, 13,
                15, 13, 9, 55, 10, 16, 8, 5, 22, 57, 24, 14, 65, 7, 50, 11, 35, 17,
                53, 31, 56, 35, 60, 40, 11, 49, 75, 13, 39, 14, 14, 27, 20, 27, 31,
                20, 20, 44, 28, 40, 17, 128, 55, 42, 11, 37, 56, 13, 13, 26, 75, 16,
                29, 18, 84, 126, 40, 20, 65, 25, 70, 37, 83, 36, 39, 91, 53, 47, 57,
                13173,
            ],
        },
        "formDetected": True,
        "numForms": 1,
        "numFormElements": 4,
        "be": {"si": False},
        "end": end_ts,
        "errors": [],
        "version": "2.3.0",
        "id": run_id,
    }

    metrics_json = json.dumps(metrics_obj, separators=(",", ":"))

    metrics_flat = {
        "f2p": f2p, "browser": browser, "capabilities": capabilities,
        "gpu": gpu, "dnt": dnt, "canvas": canvas, "be": be,
        "timestamp1": timestamp1, "timestamp2": timestamp2,
    }
    return metrics_json, metrics_flat


# ---------------------------------------------------------------------------
# HTTP calls
# ---------------------------------------------------------------------------


def _get_challenge(session: requests.Session) -> dict:
    resp = session.get(_CHALLENGE_URL, timeout=10, verify=False)
    resp.raise_for_status()
    return resp.json()


def _verify_solution(
    session: requests.Session,
    challenge: dict,
    solution: str,
    checksum: str,
    metrics_json: str,
    metrics_flat: dict[str, Any],
) -> dict:
    encrypted = _aes_gcm_encrypt(checksum + "#" + metrics_json)
    t1 = metrics_flat["timestamp1"]
    t2 = metrics_flat["timestamp2"]

    payload = {
        "challenge": challenge["challenge"],
        "solution": solution,
        "checksum": checksum,
        "existing_token": None,
        "domain": "auth.ankama.com",
        "client": "Browser",
        "signals": [
            {
                "name": "KramerAndRio",
                "value": {"Present": encrypted},
            }
        ],
        "metrics": [
            {"name": "2",   "value": 0.5608000000000288,           "unit": "2"},
            {"name": "100", "value": metrics_flat["f2p"],          "unit": "2"},
            {"name": "101", "value": metrics_flat["browser"],      "unit": "2"},
            {"name": "102", "value": metrics_flat["capabilities"], "unit": "2"},
            {"name": "103", "value": metrics_flat["gpu"],          "unit": "2"},
            {"name": "104", "value": metrics_flat["dnt"],          "unit": "2"},
            {"name": "105", "value": 0,                            "unit": "2"},
            {"name": "106", "value": 0,                            "unit": "2"},
            {"name": "107", "value": 0,                            "unit": "2"},
            {"name": "108", "value": 0,                            "unit": "2"},
            {"name": "109", "value": 0,                            "unit": "2"},
            {"name": "110", "value": 0,                            "unit": "2"},
            {"name": "111", "value": metrics_flat["canvas"],       "unit": "2"},
            {"name": "112", "value": 1,                            "unit": "2"},
            {"name": "113", "value": metrics_flat["be"],           "unit": "2"},
            {"name": "3",   "value": 13.910499999999956,           "unit": "2"},
            {"name": "7",   "value": 0,                            "unit": "4"},
            {"name": "1",   "value": t1,                           "unit": "2"},
            {"name": "4",   "value": t2,                           "unit": "2"},
            {"name": "5",   "value": 0.0013000000000147338,        "unit": "2"},
            {"name": "6",   "value": t1 + t2,                      "unit": "2"},
            {"name": "8",   "value": 1,                            "unit": "4"},
        ],
    }

    body = json.dumps(payload, separators=(",", ":"))
    resp = session.post(
        _VERIFY_URL,
        data=body.encode("utf-8"),
        headers=_VERIFY_HEADERS,
        timeout=15,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_aws_waf_token(state: str, proxy_url: str | None = None) -> str:
    """Obtain aws-waf-token for auth.ankama.com.

    `state` is the CSRF state extracted from the PKCE auth page HTML.
    Retries up to 5 times (e.g. if challenge type is unsupported or network error).
    Raises RuntimeError if all attempts fail.
    """
    from ankama_launcher_emulator.utils.proxy import to_socks5h

    session = requests.Session()
    if proxy_url:
        h_url = to_socks5h(proxy_url)
        session.proxies = {"http": h_url, "https": h_url}

    for attempt in range(5):
        try:
            challenge_resp = _get_challenge(session)
            challenge_type = challenge_resp.get("challenge_type", "")

            if challenge_type != _CHALLENGE_TYPE_SHA256:
                logger.warning(
                    "[WAF] Unknown challenge type %s on attempt %d, retrying",
                    challenge_type, attempt + 1,
                )
                continue

            difficulty = challenge_resp["difficulty"]
            input_str = challenge_resp["challenge"]["input"]

            metrics_json, metrics_flat = _generate_metrics(state)
            checksum = _crc32_checksum(metrics_json)

            logger.debug("[WAF] Solving SHA256 PoW difficulty=%d", difficulty)
            solution = _solve_sha256(input_str, checksum, difficulty)
            logger.debug("[WAF] Solution found: %s", solution)

            result = _verify_solution(
                session, challenge_resp, solution, checksum, metrics_json, metrics_flat
            )
            token = result.get("token", "")
            if not token:
                logger.warning("[WAF] Empty token on attempt %d", attempt + 1)
                continue

            logger.info("[WAF] aws-waf-token obtained")
            return token

        except Exception as exc:
            logger.warning("[WAF] Attempt %d failed: %s", attempt + 1, exc)

    raise RuntimeError("AWS WAF bypass failed after 5 attempts")

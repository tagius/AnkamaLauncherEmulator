"""Shield detection and HAAPI-based verification flow.

All calls go through the proxy session so IP stays consistent.
"""

import logging

import requests

from ankama_launcher_emulator.haapi.urls import (
    ANKAMA_SHIELD_SECURITY_CODE,
    ANKAMA_SHIELD_VALIDATE_CODE,
)
from ankama_launcher_emulator.haapi.zaap_version import ZAAP_VERSION
from ankama_launcher_emulator.utils.debug_logger import hook_session
from ankama_launcher_emulator.utils.proxy import to_socks5h

logger = logging.getLogger()


class ShieldRequired(Exception):
    """Raised when proxy IP needs Shield verification."""

    def __init__(self, login: str, proxy_url: str, game_id: int):
        self.login = login
        self.proxy_url = proxy_url
        self.game_id = game_id
        super().__init__(f"Shield verification required for {login} from proxy")


def _make_proxy_session(proxy_url: str) -> requests.Session:
    session = requests.Session()
    h_url = to_socks5h(proxy_url)
    session.proxies = {"http": h_url, "https": h_url}
    hook_session(session)
    return session


def _zaap_headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "User-Agent": f"Zaap {ZAAP_VERSION}",
        "accept": "*/*",
        "accept-encoding": "gzip,deflate",
        "accept-language": "fr",
    }


def check_proxy_needs_shield(api_key: str, proxy_url: str, game_id: int = 102) -> bool:
    """Test if proxy IP triggers Shield by calling SignOnWithApiKey.

    Returns True if Shield verification needed, False if proxy is already trusted.
    """
    session = _make_proxy_session(proxy_url)
    try:
        response = session.post(
            "https://haapi.ankama.com/json/Ankama/v5/Account/SignOnWithApiKey",
            json={"game": game_id},
            headers=_zaap_headers(api_key),
            verify=False,
        )
        if response.status_code == 403:
            logger.info("[SHIELD] Proxy IP blocked/shielded (403)")
            return True
        response.raise_for_status()
        return False
    except requests.exceptions.HTTPError:
        return True


def request_security_code(
    api_key: str,
    proxy_url: str,
    transport_type: str = "EMAIL",
) -> dict:
    """Request Ankama to send a security code via email.

    Tries GET with query params (API rejects POST with 405).
    Returns the response body dict on success.
    Raises on failure with full response details for debugging.
    """
    session = _make_proxy_session(proxy_url)
    headers = _zaap_headers(api_key)

    attempts = [
        {"transportType": transport_type},
        {"transport_type": transport_type},
        {},
    ]

    last_response = None
    for params in attempts:
        response = session.get(
            ANKAMA_SHIELD_SECURITY_CODE,
            params=params,
            headers=headers,
            verify=False,
        )
        last_response = response
        logger.info(
            f"[SHIELD] SecurityCode attempt params={params}: "
            f"status={response.status_code} body={response.text[:500]}"
        )
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return {"status": "ok", "raw": response.text}

    # All attempts failed — raise with details for debugging
    assert last_response is not None
    raise requests.exceptions.HTTPError(
        f"Shield SecurityCode failed: {last_response.status_code} — "
        f"{last_response.text[:500]}",
        response=last_response,
    )


def validate_security_code(
    api_key: str,
    proxy_url: str,
    code: str,
) -> dict:
    """Validate the security code the user received via email.

    Tries GET with query params (API rejects POST with 405).
    Returns response body dict on success.
    Raises on failure with full response details.
    """
    session = _make_proxy_session(proxy_url)
    headers = _zaap_headers(api_key)

    attempts = [
        {"code": code},
        {"validationCode": code},
    ]

    last_response = None
    for params in attempts:
        response = session.get(
            ANKAMA_SHIELD_VALIDATE_CODE,
            params=params,
            headers=headers,
            verify=False,
        )
        last_response = response
        logger.info(
            f"[SHIELD] ValidateCode attempt params={params}: "
            f"status={response.status_code} body={response.text[:500]}"
        )
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return {"status": "ok", "raw": response.text}

    assert last_response is not None
    raise requests.exceptions.HTTPError(
        f"Shield ValidateCode failed: {last_response.status_code} — "
        f"{last_response.text[:500]}",
        response=last_response,
    )

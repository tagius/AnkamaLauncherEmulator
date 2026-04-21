"""Interactive debug harness for the AWS WAF solver.

Goals
-----
1. Probe Ankama's AWS WAF `/inputs` endpoint — learn the current
   challenge_type + difficulty + payload shape.
2. Probe auth.ankama.com login page — confirm challenge URL discovery
   regex matches Ankama's deployment, and whether gokuProps is present.
3. Run current native solver (`aws_waf_bypass.get_aws_waf_token`) — baseline.
4. Run Switch3301 solver as-is (wrong AES key + signal name) — expect the
   verify to 403, but /inputs + PoW solve path works, proving the framework.
5. Run Switch3301 solver *patched* with Ankama's constants (AES key =
   93d9..., signal name = "KramerAndRio") — the real replacement attempt.
6. Run full PKCE login using the patched solver end-to-end.

The script requires: rnet, pyscrypt, structlog (in .venv already),
plus the vendored Switch3301 repo at resources/Aws-Waf-Solver/.

Usage
-----
    python tests/debug_waf.py --probe
    python tests/debug_waf.py --probe-page
    python tests/debug_waf.py --solve-native
    python tests/debug_waf.py --solve-switch
    python tests/debug_waf.py --solve-switch-patched
    python tests/debug_waf.py --solve-full
    python tests/debug_waf.py --repro-403 --proxy socks5://user:pass@host:port
    python tests/debug_waf.py --interactive     # menu-driven

Credentials come from tests/.env (ANKAMA_TEST_LOGIN/PASSWORD) when the
full PKCE flow is selected.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import sys
import traceback
import urllib3
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Vendored solver — resources/Aws-Waf-Solver/ exposes `waf.solver.solve`
_SWITCH_ROOT = _PROJECT_ROOT / "resources" / "Aws-Waf-Solver"
if _SWITCH_ROOT.exists() and str(_SWITCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_SWITCH_ROOT))

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from tests import _debug_session as dbg


# Ankama's hardcoded constants — from ankama_launcher_emulator/haapi/aws_waf_bypass.py
ANKAMA_CHALLENGE_BASE = (
    "https://3f38f7f4f368.83dbb5dc.eu-south-1.token.awswaf.com"
    "/3f38f7f4f368/e1fcfc58118e"
)
ANKAMA_INPUTS_URL  = f"{ANKAMA_CHALLENGE_BASE}/inputs?client=browser"
ANKAMA_VERIFY_URL  = f"{ANKAMA_CHALLENGE_BASE}/verify"
ANKAMA_AES_KEY_HEX = "93d9f6846b629edb2bdc4466af627d998496cb0c08f9cf043de68d6b25aa9693"
ANKAMA_SIGNAL_NAME = "KramerAndRio"
ANKAMA_DOMAIN      = "auth.ankama.com"
ANKAMA_LOGIN_PAGE  = "https://auth.ankama.com/login/ankama"


# ───────────────────────────────────────────────────────────────────────────
# Probes
# ───────────────────────────────────────────────────────────────────────────


def probe_inputs() -> int:
    """GET /inputs on Ankama's WAF endpoint. Dump raw + decoded."""
    import requests

    dbg.banner("PROBE: Ankama WAF /inputs")
    dbg.info(f"URL: {ANKAMA_INPUTS_URL}")

    headers = {
        "accept": "*/*",
        "accept-language": "fr-FR,fr;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ),
    }
    try:
        resp = requests.get(ANKAMA_INPUTS_URL, headers=headers, timeout=15, verify=False)
    except Exception as exc:
        dbg.fail(f"network error: {exc}")
        return 1

    dbg.info(f"HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except Exception:
        dbg.fail("response not JSON:")
        print(resp.text[:2000])
        return 1

    print(json.dumps(payload, indent=2)[:3000])
    print()
    dbg.banner("DECODED CHALLENGE")
    _decode_and_report_challenge(payload)
    return 0


def _decode_and_report_challenge(payload: dict) -> None:
    top_type    = payload.get("challenge_type")
    top_diff    = payload.get("difficulty")
    challenge   = payload.get("challenge", {})
    raw_input   = challenge.get("input") if isinstance(challenge, dict) else None

    dbg.info(f"top-level challenge_type = {top_type!r}")
    dbg.info(f"top-level difficulty     = {top_diff!r}")
    dbg.info(f"challenge.input (first 80 chars) = {str(raw_input)[:80]!r}")

    if not isinstance(raw_input, str):
        dbg.fail("no challenge.input string — shape unexpected")
        return

    # Switch3301 interprets challenge.input as base64(json). Our current code
    # uses it as opaque prefix. See which is right for Ankama *today*.
    try:
        decoded_bytes = base64.b64decode(raw_input, validate=False)
        decoded_json  = json.loads(decoded_bytes)
        dbg.ok("challenge.input IS base64(JSON) — Switch3301 shape")
        print(json.dumps(decoded_json, indent=2)[:1500])
        ctype = decoded_json.get("challenge_type")
        diff  = decoded_json.get("difficulty")
        dbg.info(f"decoded.challenge_type = {ctype!r}")
        dbg.info(f"decoded.difficulty     = {diff!r}")
    except Exception as exc:
        dbg.info(f"not base64-JSON ({exc}) — Ankama uses the opaque-string shape")


def probe_login_page() -> int:
    """GET the login page, run Switch3301 discovery regexes on the HTML."""
    import requests

    dbg.banner("PROBE: Ankama login page — discovery regex test")
    url = (
        f"{ANKAMA_LOGIN_PAGE}"
        "?code_challenge=x"
        "&redirect_uri=zaap://login&client_id=102&direct=true"
        "&origin_tracker=https://www.ankama-launcher.com/launcher"
    )
    dbg.info(f"GET {url}")
    headers = {
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ),
        "accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=15, verify=False)
    except Exception as exc:
        dbg.fail(f"network: {exc}")
        return 1
    dbg.info(f"HTTP {resp.status_code}, final url = {resp.url}, {len(resp.text)} bytes")

    # Reuse Switch3301's regexes
    from waf.solver import RE_CHAL_SAME, RE_CHAL_EXT, RE_CHAL_SDK, RE_GOKU

    same = RE_CHAL_SAME.search(resp.text)
    ext  = RE_CHAL_EXT.search(resp.text)
    sdk  = RE_CHAL_SDK.search(resp.text)
    goku = RE_GOKU.search(resp.text)

    dbg.info(f"RE_CHAL_SAME: {same.group(1) if same else '<none>'}")
    dbg.info(f"RE_CHAL_EXT : {ext.group(1)  if ext  else '<none>'}")
    dbg.info(f"RE_CHAL_SDK : {sdk.group(1)  if sdk  else '<none>'}")
    dbg.info(f"RE_GOKU     : {goku.group(1) if goku else '<none>'}")

    if not (same or ext or sdk):
        dbg.fail("none of the discovery regexes matched — Ankama URL is NOT in the HTML")
        dbg.info("this means we must keep the hardcoded challenge URL")
    else:
        dbg.ok("challenge URL discoverable from HTML")

    # Bonus: state + any awswaf reference
    state_match = re.search(r'name="state"\s+value="([^"]+)"', resp.text)
    dbg.info(f"CSRF state present: {bool(state_match)}")
    awswaf_hits = re.findall(r"[a-z0-9.-]+\.awswaf\.com[^\s\"'<]*", resp.text)
    if awswaf_hits:
        dbg.info("awswaf.com references found in HTML:")
        for h in sorted(set(awswaf_hits))[:10]:
            print(f"    {h}")
    else:
        dbg.info("no awswaf.com references in HTML")
    return 0


# ───────────────────────────────────────────────────────────────────────────
# Solvers
# ───────────────────────────────────────────────────────────────────────────


def solve_native() -> int:
    dbg.banner("SOLVE: native aws_waf_bypass.get_aws_waf_token")
    dbg.install_global_hook()
    from ankama_launcher_emulator.haapi.aws_waf_bypass import get_aws_waf_token

    fake_state = "x" * 32
    try:
        token = get_aws_waf_token(fake_state)
        dbg.ok(f"token = {token[:60]}…")
        return 0
    except Exception as exc:
        dbg.fail(f"native solver failed: {exc}")
        traceback.print_exc()
        return 1


def _configure_switch_solver_for_ankama(patch: bool) -> None:
    """Monkey-patch Switch3301's module-level constants to target Ankama.

    Without patch=True the solver uses booking.com-shape constants and will
    fail verify on Ankama (wrong AES key / signal name / discovery URL).
    With patch=True we override:
      - crypto.KEY   → Ankama's AES-256 key
      - signal name  → "KramerAndRio" (inside solver._build_body/_multipart)
      - discovery    → shortcut to the hardcoded Ankama challenge URL
    """
    from waf import crypto as wcrypto
    from waf import solver as wsolver

    if not patch:
        return

    wcrypto.KEY = bytes.fromhex(ANKAMA_AES_KEY_HEX)

    _orig_build_body = wsolver._build_body
    _orig_build_mp   = wsolver._build_multipart

    def _patched_build_body(domain, challenge, solution, checksum, encrypted, metrics,
                            existing_token=None, goku_props=None):
        body = _orig_build_body(domain, challenge, solution, checksum, encrypted, metrics,
                                existing_token, goku_props)
        return body.replace('"name":"Zoey"', f'"name":"{ANKAMA_SIGNAL_NAME}"')

    def _patched_build_mp(domain, challenge, solution_data, checksum, encrypted, metrics,
                          existing_token=None, goku_props=None):
        body, ct = _orig_build_mp(domain, challenge, solution_data, checksum, encrypted, metrics,
                                  existing_token, goku_props)
        return body.replace('"name":"Zoey"', f'"name":"{ANKAMA_SIGNAL_NAME}"'), ct

    wsolver._build_body      = _patched_build_body
    wsolver._build_multipart = _patched_build_mp

    # Short-circuit discovery: Ankama's challenge URL is stable, and the
    # regexes don't match the login page HTML.
    async def _patched_discover(client, site, ua):
        return ANKAMA_CHALLENGE_BASE, False, None

    wsolver._discover = _patched_discover

    dbg.info(f"[patch] crypto.KEY = {ANKAMA_AES_KEY_HEX[:16]}…")
    dbg.info(f"[patch] signal name → {ANKAMA_SIGNAL_NAME!r}")
    dbg.info(f"[patch] _discover → {ANKAMA_CHALLENGE_BASE}")


def solve_switch(patched: bool, proxy: str | None = None) -> int:
    dbg.banner(
        f"SOLVE: Switch3301 solver ({'PATCHED for Ankama' if patched else 'AS-IS — expect verify 403'})"
    )
    _configure_switch_solver_for_ankama(patched)

    from waf.solver import solve as switch_solve

    ua = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    )

    async def _run():
        # Switch3301 `solve()` expects a site, then discovers the challenge
        # URL. With our patch, discovery is short-circuited.
        return await switch_solve("https://auth.ankama.com", ua, proxy=proxy)

    try:
        result, _client = asyncio.run(_run())
        dbg.ok(f"result = {result}")
        token = result.get("token") if isinstance(result, dict) else None
        if token:
            dbg.ok(f"token = {token[:60]}…")
            return 0
        dbg.fail("no token in result — verify rejected")
        return 1
    except Exception as exc:
        dbg.fail(f"switch solver raised: {exc}")
        traceback.print_exc()
        return 1


def solve_full_pkce() -> int:
    """End-to-end login using the patched Switch3301 solver in place of
    the native `get_aws_waf_token`."""
    dbg.banner("SOLVE: full PKCE login with patched Switch3301 solver")
    dbg.load_dotenv()
    login = os.environ.get("ANKAMA_TEST_LOGIN")
    password = os.environ.get("ANKAMA_TEST_PASSWORD")
    if not login or not password:
        dbg.fail("ANKAMA_TEST_LOGIN/PASSWORD not set in tests/.env")
        return 1

    _configure_switch_solver_for_ankama(patch=True)
    from waf.solver import solve as switch_solve

    ua = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    )

    # Monkey-patch get_aws_waf_token to use the new solver
    from ankama_launcher_emulator.haapi import aws_waf_bypass, pkce_auth

    def _new_get_aws_waf_token(state: str, proxy_url: str | None = None) -> str:
        dbg.info("[shim] get_aws_waf_token called — running Switch3301 solver")
        async def _run():
            return await switch_solve("https://auth.ankama.com", ua, proxy=proxy_url)
        result, _client = asyncio.run(_run())
        token = result.get("token") if isinstance(result, dict) else None
        if not token:
            raise RuntimeError("Switch3301 solver returned no token")
        return token

    aws_waf_bypass.get_aws_waf_token = _new_get_aws_waf_token
    # pkce_auth imports the symbol lazily inside the fn; still, patch the
    # module reference too, in case something else imported it.
    pkce_auth.get_aws_waf_token = _new_get_aws_waf_token  # type: ignore[attr-defined]

    dbg.install_global_hook()

    try:
        result = pkce_auth.programmatic_pkce_login(
            login,
            password,
            on_progress=lambda m: dbg.info(f"[progress] {m}"),
        )
    except Exception as exc:
        dbg.fail(f"login failed: {exc}")
        traceback.print_exc()
        return 1

    dbg.banner("RESULT")
    for k, v in result.items():
        if k in {"access_token", "refresh_token"}:
            v = (v or "")[:24] + "…"
        dbg.ok(f"{k}: {v}")
    return 0


# ───────────────────────────────────────────────────────────────────────────
# Fresh-IP 403 reproduction + option-B fix validation
# ───────────────────────────────────────────────────────────────────────────


_PKCE_AUTH_URL_TEMPLATE = (
    ANKAMA_LOGIN_PAGE
    + "?code_challenge={cc}"
    + "&redirect_uri=zaap://login&client_id=102&direct=true"
    + "&origin_tracker=https://www.ankama-launcher.com/launcher"
)

_BROWSERY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Upgrade-Insecure-Requests": "1",
}


def repro_403(proxy: str) -> int:
    """Reproduce the fresh-IP WAF 403 through a proxy, then validate the
    option-B fix (pre-solve WAF before GET).

    Phase 1 (bug repro): plain GET /login/ankama, no WAF cookie.
        expected: HTTP 403 + CloudFront "Request blocked" body.
    Phase 2 (fix verify): call get_aws_waf_token first, inject cookie, retry GET.
        expected: HTTP 200 + CSRF state present.

    Returns 0 iff both phases match their expectation.
    """
    import requests
    from ankama_launcher_emulator.utils.proxy import to_socks5h, verify_proxy_ip

    dbg.banner("REPRO: fresh-IP /login/ankama 403 via proxy")
    dbg.info(f"proxy: {proxy}")

    try:
        exit_ip = verify_proxy_ip(proxy)
        dbg.ok(f"proxy reachable, exit IP = {exit_ip}")
    except Exception as exc:
        dbg.fail(f"proxy unreachable: {exc}")
        return 1

    socks5h = to_socks5h(proxy)
    proxies = {"http": socks5h, "https": socks5h}
    url = _PKCE_AUTH_URL_TEMPLATE.format(cc="x" * 43)

    # Phase 1 — naked GET
    dbg.banner("PHASE 1 — bug repro (GET without WAF cookie)")
    session_a = requests.Session()
    session_a.proxies = proxies
    try:
        resp_a = session_a.get(
            url, headers=_BROWSERY_HEADERS, allow_redirects=True, timeout=20, verify=False,
        )
    except Exception as exc:
        dbg.fail(f"network error: {exc}")
        return 1

    body_a = resp_a.text or ""
    dbg.info(f"HTTP {resp_a.status_code}, {len(body_a)} bytes, url = {resp_a.url}")
    state_a = re.search(r'name="state"\s+value="([^"]+)"', body_a)
    awswaf_hits = re.findall(r"[a-z0-9.-]+\.awswaf\.com", body_a)
    is_cloudfront_block = (
        resp_a.status_code == 403
        and ("Request blocked" in body_a or "could not be satisfied" in body_a)
    )
    is_waf_challenge = bool(awswaf_hits) and not state_a

    if state_a:
        dbg.fail("phase 1 got CSRF state — proxy IP is already trusted, cannot repro")
        dbg.info("try a different proxy exit to get a fresh/flagged IP")
        return 1
    if is_cloudfront_block:
        dbg.ok("phase 1 matches bug signature: 403 CloudFront block (no CSRF)")
    elif is_waf_challenge:
        dbg.ok(
            f"phase 1 matches bug signature: WAF challenge page "
            f"(status={resp_a.status_code}, awswaf refs: {sorted(set(awswaf_hits))[:3]})"
        )
    else:
        dbg.fail(
            f"phase 1 unexpected: status={resp_a.status_code}, "
            f"no CSRF, no awswaf refs. body head={body_a[:200]!r}"
        )
        return 1

    # Phase 2 — pre-solve WAF, inject cookie, retry GET
    dbg.banner("PHASE 2 — fix verify (pre-solve WAF, then GET)")
    from ankama_launcher_emulator.haapi.aws_waf_bypass import get_aws_waf_token

    try:
        token = get_aws_waf_token("", proxy_url=proxy)
    except Exception as exc:
        dbg.fail(f"WAF solver failed: {exc}")
        traceback.print_exc()
        return 1
    dbg.ok(f"aws-waf-token obtained (len={len(token)}, head={token[:24]}…)")

    session_b = requests.Session()
    session_b.proxies = proxies
    session_b.cookies.set("aws-waf-token", token, domain="auth.ankama.com", path="/")
    try:
        resp_b = session_b.get(
            url, headers=_BROWSERY_HEADERS, allow_redirects=True, timeout=20, verify=False,
        )
    except Exception as exc:
        dbg.fail(f"network error on retry: {exc}")
        return 1

    body_b = resp_b.text or ""
    dbg.info(f"HTTP {resp_b.status_code}, {len(body_b)} bytes, url = {resp_b.url}")
    state_b = re.search(r'name="state"\s+value="([^"]+)"', body_b)

    if resp_b.status_code == 200 and state_b:
        dbg.ok(f"phase 2 success: 200 + CSRF state (len={len(state_b.group(1))})")
        dbg.banner("VERDICT")
        dbg.ok("option B confirmed: pre-solving WAF yields a good CSRF page")
        return 0

    dbg.fail(
        f"phase 2 failed: status={resp_b.status_code}, "
        f"csrf_present={bool(state_b)}, body head={body_b[:200]!r}"
    )
    return 1


# ───────────────────────────────────────────────────────────────────────────
# Interactive menu
# ───────────────────────────────────────────────────────────────────────────


_MENU = """
  [1] probe /inputs           — dump AWS WAF challenge shape
  [2] probe login page        — test Switch3301 discovery regexes on Ankama
  [3] solve native            — run current aws_waf_bypass solver
  [4] solve Switch3301 as-is  — wrong key, expected 403 (framework check)
  [5] solve Switch3301 patched— Ankama key + signal name
  [6] solve full PKCE         — full login using patched solver
  [7] repro 403 + verify fix  — fresh-IP 403 repro via proxy, option-B validation
  [q] quit
"""


def interactive() -> int:
    while True:
        print(_MENU)
        choice = input("choice> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return 0
        try:
            if choice == "1":
                probe_inputs()
            elif choice == "2":
                probe_login_page()
            elif choice == "3":
                solve_native()
            elif choice == "4":
                solve_switch(patched=False)
            elif choice == "5":
                solve_switch(patched=True)
            elif choice == "6":
                solve_full_pkce()
            elif choice == "7":
                proxy = input("proxy (socks5://user:pass@host:port)> ").strip()
                if proxy:
                    repro_403(proxy)
                else:
                    print("no proxy given — skipped")
            else:
                print(f"unknown: {choice!r}")
        except KeyboardInterrupt:
            print("^C — back to menu")
        print()


# ───────────────────────────────────────────────────────────────────────────
# Entry
# ───────────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe",                action="store_true", help="dump /inputs")
    p.add_argument("--probe-page",           action="store_true", help="test discovery regexes on Ankama login")
    p.add_argument("--solve-native",         action="store_true", help="run current solver")
    p.add_argument("--solve-switch",         action="store_true", help="run Switch3301 as-is")
    p.add_argument("--solve-switch-patched", action="store_true", help="run Switch3301 with Ankama key+name")
    p.add_argument("--solve-full",           action="store_true", help="full PKCE login with patched solver")
    p.add_argument("--repro-403",            action="store_true", help="reproduce fresh-IP 403 + verify option-B fix (requires --proxy)")
    p.add_argument("--proxy",                help="socks5://host:port or http://host:port")
    p.add_argument("--interactive", "-i",    action="store_true", help="menu mode")
    args = p.parse_args()

    if args.interactive or not any([
        args.probe, args.probe_page, args.solve_native,
        args.solve_switch, args.solve_switch_patched, args.solve_full,
        args.repro_403,
    ]):
        return interactive()

    rc = 0
    if args.probe:                rc |= probe_inputs()
    if args.probe_page:           rc |= probe_login_page()
    if args.solve_native:         rc |= solve_native()
    if args.solve_switch:         rc |= solve_switch(patched=False, proxy=args.proxy)
    if args.solve_switch_patched: rc |= solve_switch(patched=True,  proxy=args.proxy)
    if args.solve_full:           rc |= solve_full_pkce()
    if args.repro_403:
        if not args.proxy:
            dbg.fail("--repro-403 requires --proxy")
            return 1
        rc |= repro_403(args.proxy)
    return rc


if __name__ == "__main__":
    sys.exit(main())

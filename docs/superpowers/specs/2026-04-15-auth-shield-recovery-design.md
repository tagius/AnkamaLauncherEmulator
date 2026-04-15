# Auth And Shield Recovery Design

## Summary

Fix the launcher's two broken auth paths while keeping the embedded-browser direction:

- adding a new account
- recovering an already-added account after IP/proxy change

The design is based on three inputs:

1. current launcher code
2. `resources/dofus-multi` as a reference for first-time add-account and initial Shield enrollment
3. decompiled launcher references in `resources/Authent_launcher.py`, `resources/HaapiService.cs`, and `resources/CertificateService.cs`

The core conclusion is that the current launcher conflates two different flows:

- browser-based login / PKCE code capture
- HAAPI Shield code and certificate generation

Those need to be represented explicitly and separately in both code and UI.

## Goals

- Restore add-account on packaged Windows builds.
- Keep the embedded-browser approach as the primary login UX.
- Make the add-account flow match the launcher pattern more closely.
- Replace the current IP-change assumption with an explicit recovery path when trust has to be re-established.
- Preserve the existing stored keydata and certificate formats unless a real mismatch is discovered.

## Non-Goals

- No switch to a permanent system-browser-only auth model in this pass.
- No redesign of the general launcher UI.
- No official-launcher lab implementation in this spec.
- No attempt to fully reproduce every private launcher behavior not supported by evidence.

## Evidence

### Decompiled Launcher

`resources/HaapiService.cs` shows a reconnect flow based on `CreateApiKey(login, password, game_id, certificate_id, certificate_hash)` first. If the returned `securityState` is not `UNSECURED`, the code immediately calls `Account/CreateToken` with the resulting API key and the certificate data. If the state is `UNSECURED`, it triggers certificate generation and retries the full connect sequence.

`resources/CertificateService.cs` shows certificate generation as a separate HAAPI interaction:

- `Shield/SecurityCode`
- user enters the e-mail code
- `Shield/ValidateCode?hm1=...&hm2=...&name=...&code=...&game_id=...`

`resources/Authent_launcher.py` shows the login browser flow as a separate concern:

- open Ankama login page
- obtain `state`
- submit credentials in browser
- capture `zaap://login?code=...`
- exchange code on `/token`

### dofus-multi

`dofus-multi` is still useful for:

- PKCE parameter shape
- first-time add-account flow
- initial `Shield/SecurityCode` and `Shield/ValidateCode`
- storing random `hm1/hm2` alongside the returned certificate

It is not a reliable reference for IP-change recovery because it does not model the launcher's `CreateApiKey -> possible re-Shield -> retry` structure.

### Current Launcher Code

Current problems:

- packaged app crashes when the embedded browser fallback imports `PyQt6.QtWebEngineCore`
- the current IP-change path assumes `stored certificate => skip Shield`
- after Shield validation, relaunch still goes straight to `CreateToken`, which can return `403`

## Selected Direction

Keep the embedded browser, but formalize two separate dialogs and two separate auth responsibilities.

1. `EmbeddedAuthBrowserDialog`
   - responsible only for Ankama login and PKCE redirect capture
   - captures `zaap://login?code=...`
   - never asks for the Shield mail code

2. `ShieldCodeDialog`
   - responsible only for the e-mail verification code
   - used after HAAPI requests `Shield/SecurityCode`

This preserves the embedded UX while matching the decompiled launcher model more closely.

## Architecture

### Auth Responsibilities

Split auth logic into three layers:

1. PKCE login layer
   - builds auth URL
   - opens embedded browser
   - captures redirect code
   - exchanges code for access token / refresh token
   - fetches account profile

2. Shield service layer
   - requests `Shield/SecurityCode`
   - validates the e-mail code
   - stores updated certificate
   - returns the updated trust material

3. Launch recovery layer
   - attempts launch with existing stored data
   - detects trust failure from `CreateToken`
   - transitions into explicit recovery instead of silently retrying or launching anyway

### UI Responsibilities

`AddAccountDialog`
- owns account creation and first-time Shield enrollment
- opens embedded login dialog when headless login is blocked
- then opens `ShieldCodeDialog` only if Shield is actually required

`MainWindow`
- owns post-account-recovery during launch
- when launch trust fails, it should guide the user through:
  - re-login in embedded browser
  - e-mail Shield code entry
  - certificate refresh
  - retry launch

`shield_browser_dialog.py`
- should be treated as the login dialog implementation, despite the current file name
- naming may be updated in implementation if that improves clarity

## Add-Account Flow

### Desired Flow

1. User enters login/password.
2. Launcher tries the existing programmatic PKCE path.
3. If the auth site blocks headless scraping, launcher opens the embedded browser login dialog.
4. Embedded browser captures `zaap://login?code=...`.
5. Launcher exchanges code for API key and fetches account profile.
6. If account security requires Shield:
   - call `Shield/SecurityCode`
   - open `ShieldCodeDialog`
   - call `Shield/ValidateCode`
   - store certificate and matching metadata
7. Store keydata and metadata.

### Required Constraints

- embedded browser must be packageable on Windows
- browser dialog must degrade cleanly if QtWebEngine is unavailable at runtime
- add-account must no longer depend on HTML scraping alone

## IP-Change Recovery Flow

### Problem Statement

The current path assumes:

- certificate exists locally
- therefore Shield can be skipped
- therefore launch can proceed directly to `CreateToken`

That assumption is contradicted by the observed `CreateToken 403` after IP/proxy change.

### Desired Flow

1. Launch begins normally with stored keydata and stored certificate.
2. Launcher attempts `CreateToken`.
3. If `CreateToken` succeeds, continue normally.
4. If `CreateToken` returns `403` in a certificate-bearing launch:
   - stop launch
   - treat this as a trust recovery path, not a generic transient error
5. Recovery path:
   - ask the user to log in again in the embedded browser
   - exchange the redirect code for a fresh API key
   - request `Shield/SecurityCode`
   - prompt for the e-mail code
   - call `Shield/ValidateCode`
   - store refreshed certificate and updated keydata
6. Retry launch once using the refreshed trust material.

### Important Deliberate Choice

The recovery path should not rely only on the old stored API key.

Reason:
- the decompiled launcher references suggest a credentialed reconnect flow before retrying token creation
- the current launcher path that avoids re-login is exactly the path now failing

## Certificate And Metadata Model

Continue storing:

- encrypted API key data in keydata
- encrypted certificate in the certificate directory
- launcher metadata in `account_meta.json`

Keep `hm1` in metadata as the source of `hm2` by reversal for compatibility with the current code and `dofus-multi`.

On successful recovery:

- update stored access token / refresh token
- overwrite the stored certificate for that login
- overwrite the stored `hm1` if a new one was used during validation

## Packaging Design

The embedded browser path requires explicit packaging support.

### Requirements

- PyInstaller spec must include QtWebEngine hidden imports
- packaged build must include the QtWebEngine runtime pieces needed by `QWebEngineView`
- runtime import failure must be caught and surfaced as a launcher error message rather than a traceback

### Fallback Policy

If QtWebEngine cannot be imported at runtime:

- do not crash
- report that embedded login is unavailable in this build
- keep the app responsive

This fallback is defensive only. The primary path remains embedded.

## Error Handling

### Add-Account

- Headless PKCE block: switch to embedded browser flow.
- Embedded browser unavailable: show a clear runtime error about missing embedded browser support.
- Login cancelled: return to dialog without partial account creation.
- Shield code invalid: allow retry without corrupting stored state.

### IP-Change Recovery

- `CreateToken 403` after certificate usage: enter recovery path.
- Recovery cancelled: abort launch cleanly.
- Shield code invalid during recovery: allow retry without launching.
- Recovery succeeds but retry still fails: show full error and keep account state untouched except for confirmed updates.

## Testing

### Automated

Add tests for:

- add-account switches to embedded login when headless PKCE is blocked
- runtime import failure for embedded browser is handled without crashing
- `CreateToken 403` in certificate-bearing launch enters recovery mode
- successful recovery updates stored state and retries launch once

### Manual

Manual verification cases:

1. add a new non-Shield account
2. add a new Shielded account
3. launch an existing account on same network
4. launch an existing account after proxy/IP change that forces trust recovery
5. packaged Windows build opens embedded browser successfully

## Open Questions

- Whether the current launcher should reintroduce a full `CreateApiKey(login, password, certificate_id, certificate_hash)` style reconnect helper instead of expressing recovery through PKCE-first primitives.
- Whether Retro requires distinct recovery handling beyond the `game_id` differences already present.

These do not block implementation of the selected direction because the immediate broken behavior is already localized and the UI contract is clear.

## Implementation Boundaries

Implementation should be limited to:

- auth dialog / browser integration
- add-account flow
- shield service / recovery wiring
- launch recovery orchestration
- PyInstaller packaging updates
- regression tests

Do not expand this work into the official-launcher lab in the same implementation plan.

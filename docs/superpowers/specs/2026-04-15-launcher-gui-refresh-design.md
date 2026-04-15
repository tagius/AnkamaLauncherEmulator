# Launcher GUI Refresh Design

## Summary

Refresh the PyQt6 launcher UI so it feels like a clean, modern, dark desktop application instead of a development tool. Keep the current feature set and launch flows intact, avoid new dependencies, and preserve the current single-window model. Apply the new `resources/app.ico` both at runtime and in the Windows binary produced by the GitHub Actions build.

The design direction is utility-first with subtle Ankama-inspired branding. The UI should stay dense enough for power use, especially in the account list, while improving hierarchy, spacing, and visual consistency. Stronger branding or a richer game presentation may be added later without requiring another shell redesign.

## Goals

- Keep the launcher as a single-window dashboard.
- Move game selection to a left vertical rail.
- Preserve fully configurable account cards in the main list.
- Improve the dark theme using restrained accent color `#d25f04`.
- Integrate `resources/app.ico` into both the running app and the PyInstaller-built Windows executable.
- Avoid backend behavior changes unless required by the visual restructuring.

## Non-Goals

- No new launcher features.
- No redesign of proxy, add-account, Shield, or launch flows beyond visual integration.
- No new third-party UI or styling dependencies.
- No large branded hero/artwork area in this pass.
- No changes to the existing GitHub Actions workflow shape beyond using the icon through `main.spec`.

## Constraints

- Use existing PyQt6 and `qfluentwidgets`.
- Keep changes tightly scoped to the user request.
- Respect the dirty worktree and avoid touching unrelated modifications.
- Keep room in the shell for future incremental branding additions.

## Selected Direction

The approved direction is `Utility Dashboard`.

Characteristics:

- Single-window dashboard.
- Left rail for game selection.
- Mostly utility with subtle branding.
- Fully configurable account cards remain in the main list.
- More branding can be layered in later without changing the shell structure.

## Window Architecture

The main window becomes a clearer dashboard shell with four visual regions:

1. Left rail
   - Narrow vertical column for game switching.
   - Uses compact icon-based buttons for `Dofus 3` and `Dofus Rétro`.
   - Bottom slot reserved for future utility actions such as settings or about.

2. Top control bar
   - Shows the selected game name and compact status summary.
   - Holds global actions on the right: `Proxies` and `Add Account`.
   - Replaces the loose horizontal selector row used today.

3. Status/update strip
   - Slim integrated panel under the top bar.
   - Hidden by default.
   - Expands only for download/update progress or important warnings.

4. Main content area
   - Scrollable account list occupying the primary space.
   - Empty states and warnings render in this region as styled panels instead of plain labels.

This shell keeps the current one-window workflow, creates stronger visual structure, and avoids adding navigation complexity.

## Component Design

### MainWindow

`MainWindow` remains the composition root and is responsible for arranging the new shell:

- left rail
- top control bar
- conditional status strip
- scrollable account region

It should continue to own game selection, progress/status updates, and dialog entry points. The redesign is structural and presentational, not a rewrite of launch behavior.

### Game Selector

The current `GameSelectorCard` should be reshaped into a compact rail button:

- icon-first presentation
- stronger selected state
- subdued inactive state
- disabled state for unavailable games

It should stop reading like a wide content card and instead behave like navigation within the dashboard shell.

### Account Cards

`AccountCard` keeps all current controls visible in the main list:

- account identity
- interface selection
- proxy selection
- proxy test action
- launch/stop action

The change is visual organization, not feature reduction. The layout should become more readable by:

- giving the account identity a clearer anchor position
- grouping network controls consistently
- making `Launch` the primary action
- making `Test` visually secondary
- improving running-state visibility

Dense operation is intentional and should be preserved.

### Download / Status Strip

`DownloadBanner` should become a slimmer, integrated strip that fits the new shell:

- hidden when idle
- clear progress when active
- visually consistent with the new dashboard panels

It should feel like part of the application layout rather than a temporary development widget.

### Empty and Warning Panels

The current plain labels for missing accounts and missing optional tooling should become dedicated panels rendered in the main content area:

- centered or well-framed
- visually distinct from normal account cards
- readable without looking like debug output

## Styling

### Visual Tone

- Dark charcoal foundation.
- Subtle panel elevation and restrained borders.
- Clean spacing and clearer hierarchy.
- Accent color limited to purposeful use.

### Accent Usage

Use `#d25f04` for:

- selected game in the left rail
- primary actions such as `Launch` and `Add Account`
- progress fills and active highlights

Avoid using the accent as a background color for large surfaces.

### Branding

Branding should stay subtle in this pass:

- runtime window icon
- game naming and iconography
- restrained use of existing game assets where they help orientation

No large art-heavy header is part of this scope.

## Behavior

The redesign must preserve familiar launcher behavior.

### Game Selection

- Selecting a game from the left rail updates the selected title and current launch target.
- No secondary page or view switch should appear.
- The account list remains in place.

### Global Actions

- `Proxies` continues opening the proxy dialog.
- `Add Account` continues opening the add-account flow.
- Their placement changes, not their meaning.

### Account States

The UI should read clearly across these states:

- idle
- launching
- running
- update in progress
- error

The affected account should be visually identifiable. The rest of the window should remain usable unless a genuinely global state requires otherwise.

### Status Presentation

The top status area should stay quiet unless needed:

- update/download activity
- missing-install warnings
- blocking issues such as Shield or proxy failures

This prevents the app from feeling noisy while keeping operational feedback visible when necessary.

## Error Handling

No new backend error flows are required. The design only improves presentation and clarity.

Expected behavior:

- Missing accounts render as a proper empty-state panel with guidance and expected path details.
- Missing `cytrus-v6` renders as a styled warning panel.
- Launch/proxy/Shield errors continue through existing logic.
- After failures, account controls re-enable cleanly and the status strip does not remain stuck visible.

## Icon and Build Integration

### Runtime Icon

At app startup:

- load `resources/app.ico`
- apply it as the Qt application/window icon

This ensures the running launcher window reflects the new icon.

### Windows Binary

Update `main.spec` so PyInstaller uses `resources/app.ico` for the generated executable.

The existing GitHub Actions workflow at `.github/workflows/build-windows.yml` should remain simple:

- install dependencies
- run `pyinstaller main.spec`
- upload the built executable

The icon integration should happen through the spec file instead of custom workflow logic.

## Implementation Boundaries

Files likely in scope:

- `ankama_launcher_emulator/gui/app.py`
- `ankama_launcher_emulator/gui/main_window.py`
- `ankama_launcher_emulator/gui/account_card.py`
- `ankama_launcher_emulator/gui/game_selector_card.py`
- `ankama_launcher_emulator/gui/download_banner.py`
- `ankama_launcher_emulator/gui/consts.py`
- `main.spec`

Files not in scope unless required by verification:

- launch backend logic
- proxy backend logic
- server behavior
- auth/decryption flows

## Verification Criteria

Implementation is complete only if all of the following are true:

1. The application starts successfully with the redesigned shell.
2. The UI renders the left rail, top control bar, conditional status strip, and scrollable account list.
3. Game switching still works for both supported games.
4. Existing dialogs still open from the redesigned shell.
5. Account launch, stop, and proxy test interactions still work.
6. Empty-state and warning-state layouts render correctly.
7. The runtime window icon is loaded from `resources/app.ico`.
8. `main.spec` is configured so the Windows executable built by GitHub Actions uses the same icon.
9. No new dependencies are introduced.

## Risks

- The current widgets may carry styling assumptions that do not fit the new shell cleanly, especially `GameSelectorCard` and `AccountCard`.
- Dense account-card layouts can become cramped if spacing and width allocation are not handled carefully.
- Runtime icon handling and PyInstaller icon configuration must both be updated; doing only one would produce an inconsistent result.

## Incremental Follow-Up

This shell should allow future visual additions without architectural change, such as:

- richer selected-game summary
- restrained logo treatment
- optional artwork or news modules
- additional utility actions in the left rail

Those future additions are intentionally excluded from this implementation scope.

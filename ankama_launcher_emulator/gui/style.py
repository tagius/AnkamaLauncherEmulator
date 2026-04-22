from PyQt6.QtWidgets import QApplication


_APP_STYLE_MARKER = "/* AnkAlt shared control style */"

APP_CONTROL_STYLESHEET = f"""
{_APP_STYLE_MARKER}
PushButton, PrimaryPushButton, ComboBox {{
    min-height: 32px;
    border-radius: 16px;
    padding: 6px 14px;
}}

ComboBox {{
    padding-left: 14px;
    padding-right: 30px;
}}

ComboBoxMenu, RoundMenu {{
    border-radius: 12px;
}}

QListView#comboListWidget, ListWidget#comboListWidget {{
    border-radius: 12px;
    padding: 4px 0;
}}
"""


def apply_app_style(app: QApplication) -> None:
    current = app.styleSheet()
    if _APP_STYLE_MARKER in current:
        return

    separator = "\n" if current else ""
    app.setStyleSheet(f"{current}{separator}{APP_CONTROL_STYLESHEET}")

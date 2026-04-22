from PyQt6.QtWidgets import QApplication


_APP_STYLE_MARKER = "/* AnkAlt shared control style */"

APP_CONTROL_STYLESHEET = f"""
{_APP_STYLE_MARKER}
PushButton, PrimaryPushButton, ComboBox, LineEdit, PasswordLineEdit {{
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    padding: 2px 10px;
}}

ComboBox {{
    padding-left: 10px;
    padding-right: 26px;
}}

ComboBoxMenu, RoundMenu {{
    border-radius: 14px;
}}

QListView#comboListWidget, ListWidget#comboListWidget {{
    border-radius: 14px;
    padding: 2px 0;
}}

QListView#comboListWidget::item, ListWidget#comboListWidget::item {{
    min-height: 26px;
    padding: 2px 10px;
}}
"""


def apply_app_style(app: QApplication) -> None:
    current = app.styleSheet()
    if _APP_STYLE_MARKER in current:
        return

    separator = "\n" if current else ""
    app.setStyleSheet(f"{current}{separator}{APP_CONTROL_STYLESHEET}")

from PyQt6.QtWidgets import QDialog, QVBoxLayout
from qfluentwidgets import BodyLabel, LineEdit, PrimaryPushButton, PushButton


class ShieldCodeDialog(QDialog):
    """Dialog asking user for Ankama Shield security code.

    A security code has been sent to the user's email.
    They enter it here, we validate via HAAPI through the proxy.
    """

    def __init__(self, login: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shield Verification")
        self.setMinimumWidth(400)
        self._code: str | None = None
        self._setup_ui(login)

    def _setup_ui(self, login: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = BodyLabel(
            f"New proxy IP detected for {login}.\n\n"
            "Ankama sent a security code to your email.\n"
            "Enter it below to authorize this proxy."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._code_input = LineEdit()
        self._code_input.setPlaceholderText("Security code from email")
        self._code_input.returnPressed.connect(self._on_submit)
        layout.addWidget(self._code_input)

        self._submit_btn = PrimaryPushButton("Validate")
        self._submit_btn.clicked.connect(self._on_submit)
        layout.addWidget(self._submit_btn)

        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _on_submit(self) -> None:
        code = self._code_input.text().strip()
        if not code:
            return
        self._code = code
        self.accept()

    def get_code(self) -> str | None:
        return self._code

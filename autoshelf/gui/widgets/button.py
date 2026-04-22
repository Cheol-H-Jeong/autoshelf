from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QPushButton

from autoshelf.gui.design import ICON_SIZE
from autoshelf.gui.icons import icon


class BaseButton(QPushButton):
    def __init__(self, text: str = "", icon_name: str = "", role: str = "secondary") -> None:
        super().__init__(text)
        self._normal_text = text
        self._role = role
        self.setProperty("buttonRole", role)
        self.setCursorRole()
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        if icon_name:
            self.setIcon(icon(icon_name))
        self.setAccessibleName(text or role)
        self.setAccessibleDescription(text or role)
        if role == "primary":
            self.setObjectName("primaryAction")
            self.setDefault(True)

    def setCursorRole(self) -> None:
        self.setProperty("class", "button")

    def setLoading(self, loading: bool, text: str | None = None) -> None:
        self.setEnabled(not loading)
        label = (
            text if loading and text is not None else ("처리 중" if loading else self._normal_text)
        )
        self.setText(label)

    def setText(self, text: str) -> None:  # noqa: N802
        self._normal_text = (
            text if not text.startswith("처리 중") else getattr(self, "_normal_text", text)
        )
        super().setText(text)
        if text:
            self.setAccessibleName(text)


class PrimaryButton(BaseButton):
    def __init__(self, text: str = "", icon_name: str = "") -> None:
        super().__init__(text, icon_name, "primary")


class SecondaryButton(BaseButton):
    def __init__(self, text: str = "", icon_name: str = "") -> None:
        super().__init__(text, icon_name, "secondary")


class GhostButton(BaseButton):
    def __init__(self, text: str = "", icon_name: str = "") -> None:
        super().__init__(text, icon_name, "ghost")


class DangerButton(BaseButton):
    def __init__(self, text: str = "", icon_name: str = "") -> None:
        super().__init__(text, icon_name, "danger")

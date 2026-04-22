from __future__ import annotations

from dataclasses import dataclass

SPACE_4 = 4
SPACE_8 = 8
SPACE_16 = 16
SPACE_24 = 24
SPACE_32 = 32
SPACE_48 = 48
SPACE_64 = 64

RADIUS_8 = 8
RADIUS_12 = 12
FOCUS_RING = 2
BORDER_1 = 1
BORDER_2 = 2

FONT_11 = 11
FONT_13 = 13
FONT_15 = 15
FONT_18 = 18
FONT_24 = 24
FONT_32 = 32

BUTTON_HEIGHT = 40
BUTTON_HEIGHT_LARGE = 48
ICON_SIZE = 20
TOAST_DURATION_MS = 4000
MOTION_FAST_MS = 150
MOTION_LAYOUT_MS = 200


@dataclass(frozen=True)
class Palette:
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    surface: str
    surface_muted: str
    surface_raised: str
    app_bg: str
    border: str
    text: str
    text_muted: str
    danger: str
    success: str
    warning: str
    info: str
    focus: str


LIGHT = Palette(
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_pressed="#1E40AF",
    accent_text="#FFFFFF",
    surface="#FFFFFF",
    surface_muted="#F3F4F6",
    surface_raised="#F9FAFB",
    app_bg="#F6F8FB",
    border="#D1D5DB",
    text="#111827",
    text_muted="#4B5563",
    danger="#B91C1C",
    success="#047857",
    warning="#92400E",
    info="#1D4ED8",
    focus="#2563EB",
)

DARK = Palette(
    accent="#60A5FA",
    accent_hover="#93C5FD",
    accent_pressed="#BFDBFE",
    accent_text="#0B1220",
    surface="#172027",
    surface_muted="#1F2A33",
    surface_raised="#22313A",
    app_bg="#172027",
    border="#3A4651",
    text="#F9FAFB",
    text_muted="#D1D5DB",
    danger="#FCA5A5",
    success="#86EFAC",
    warning="#FCD34D",
    info="#93C5FD",
    focus="#93C5FD",
)

PALETTES = {"light": LIGHT, "dark": DARK}

TEXT_ON_BG_PAIRS = (
    ("text", "surface"),
    ("text", "surface_muted"),
    ("text", "surface_raised"),
    ("text", "app_bg"),
    ("text_muted", "surface"),
    ("accent_text", "accent"),
    ("danger", "surface"),
    ("success", "surface"),
    ("warning", "surface"),
    ("info", "surface"),
)

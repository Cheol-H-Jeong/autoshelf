from __future__ import annotations


def contrast_ratio(foreground: str, background: str) -> float:
    fg = _relative_luminance(_hex_to_rgb(foreground))
    bg = _relative_luminance(_hex_to_rgb(background))
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    normalized = value.strip().lstrip("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {value!r}")
    return tuple(int(normalized[index : index + 2], 16) / 255 for index in (0, 2, 4))


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    channels = []
    for channel in rgb:
        if channel <= 0.03928:
            channels.append(channel / 12.92)
        else:
            channels.append(((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue

import pytest

from autoshelf.gui.contrast import contrast_ratio
from autoshelf.gui.design import (
    FONT_11,
    FONT_13,
    FONT_15,
    FONT_18,
    FONT_24,
    FONT_32,
    MOTION_FAST_MS,
    MOTION_LAYOUT_MS,
    PALETTES,
    SPACE_4,
    SPACE_8,
    SPACE_16,
    SPACE_24,
    SPACE_32,
    SPACE_48,
    SPACE_64,
    TEXT_ON_BG_PAIRS,
)


def test_palette_text_contrast_is_wcag_aa():
    for palette in PALETTES.values():
        for foreground, background in TEXT_ON_BG_PAIRS:
            assert contrast_ratio(getattr(palette, foreground), getattr(palette, background)) >= 4.5


@pytest.mark.parametrize(
    "token", [SPACE_4, SPACE_8, SPACE_16, SPACE_24, SPACE_32, SPACE_48, SPACE_64]
)
def test_spacing_tokens_follow_four_point_grid(token):
    assert token % 4 == 0


@pytest.mark.parametrize("palette_name", ["light", "dark"])
def test_palette_colors_use_hex_triplets(palette_name):
    palette = PALETTES[palette_name]
    for value in palette.__dict__.values():
        assert value.startswith("#")
        assert len(value) == 7


def test_font_scale_is_strictly_increasing():
    assert [FONT_11, FONT_13, FONT_15, FONT_18, FONT_24, FONT_32] == sorted(
        [FONT_11, FONT_13, FONT_15, FONT_18, FONT_24, FONT_32]
    )


def test_motion_tokens_stay_short_and_ordered():
    assert 0 < MOTION_FAST_MS < MOTION_LAYOUT_MS <= 200

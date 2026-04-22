# autoshelf GUI design

autoshelf v2.1 uses one primary path per screen. Each top-level screen exposes exactly one dominant primary action with the `primaryAction` object name; secondary actions are outlined or quiet, and tertiary actions belong in menus.

Design tokens live in `autoshelf/gui/design.py`. Spacing follows an 8 pt grid with 4 pt reserved for compact inline controls and 24 pt or larger for hero sections. Type uses the 11 / 13 / 15 / 18 / 24 / 32 scale. Tables and progress numbers use tabular digits where supported by the platform font.

Colors are defined once as light and dark `Palette` values. Widget code should consume palette names and shared widgets rather than hardcoding hex colors. The accent is a calm blue and all text-on-surface pairs are covered by contrast tests through `autoshelf.gui.contrast`.

Icons use the bundled Lucide SVG subset in `resources/icons/lucide/`, with MIT license text included beside the icons. GUI code resolves icons through `autoshelf.gui.icons.icon()`.

Motion is short: 150 ms for fades and spinners, 200 ms for layout changes, and no long animation. The app follows system light/dark preference and keeps reduced-motion-friendly interactions.

Errors appear as persistent banners with a short Korean headline and details available on demand. Empty states include an icon, one-line headline, one-line hint, and a corrective action when the screen has no content.

Keyboard operation is required for every screen. Buttons, inputs, tabs, tables, and trees must have accessible names. `Ctrl+?` shows the shortcut summary.

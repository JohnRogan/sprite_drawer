# Sprite Drawer — Knowledge Base

> This is the living knowledge base for the Sprite Drawer tool. Per the
> always-on Cursor rule in `.cursor/rules/knowledge-base.mdc`, read this file
> before making any code changes and update it afterwards.

Last updated: 2026-09-23 (scripts moved to installation/, .gitignore added)

## What this is

An in-house PySide6 desktop pixel-art sprite editor for game development,
built to avoid paid tooling. Sprites have arbitrary dimensions, are drawn
with MS Paint-style tools, and save as PNG (Unity's best-supported sprite
format — lossless with full alpha). A real photo can be underlaid beneath
the pixel grid at adjustable opacity/scale/offset for tracing.

## Running

```bash
.venv/bin/python main.py     # venv at repo root, Python 3.14
                             # deps: PySide6 >= 6.11, Pillow, pillow-heif
```

End-user setup (non-technical users) is documented in `README.md` (one
collapsible `<details>` section per OS, since GitHub markdown has no real
tabs) and `CONTROLS.md` (new sprite, underlay, all shortcuts). Scripts:

All four scripts live in `installation/` and `cd` to the parent (project
root) first, so they work no matter where they are launched from.

- `install_windows.bat` / `install_mac.command`: find Python 3.14, or install
  3.14.3 from python.org (Windows: silent per-user install, amd64 or arm64,
  no admin; macOS: official .pkg via `sudo installer`), then (re)create
  `.venv` if missing or not 3.14, `pip install -r requirements.txt`, and
  verify the imports. Safe to re-run.
- `run_windows.bat` / `run_mac.command`: launch `main.py` from `.venv`.
- macOS users run scripts as `bash <dragged file>` in Terminal, which
  sidesteps Gatekeeper quarantine and missing execute bits on ZIP downloads.
- `.gitattributes` pins `*.bat` to CRLF (cmd.exe `goto`/labels misbehave with
  LF) and `*.command` to LF.
- Keep `CONTROLS.md` in sync when shortcuts or panel labels change.

Regression check (headless, ~2s):

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python smoke_test.py
```

`smoke_test.py` covers document undo/redo, every drawing primitive (line,
rect, ellipse, flood fill, brush stamp, clipping), PNG roundtrip, sidecar
save/restore, hex color parsing, and a pencil stroke through the real tool
protocol. Run it after any change to `sprite_drawer/`.

## Architecture

```
main.py                      entry point (QApplication + MainWindow)
sprite_drawer/
  app.py         MainWindow: menus, left toolbar (tools + brush size),
                 right docks (Colors, Trace Underlay), status bar, file I/O
  document.py    SpriteDocument (QObject): QImage Format_ARGB32 pixel store,
                 snapshot undo/redo (MAX_UNDO=64), dirty flag, load/save PNG.
                 Signals: changed, modified_changed, document_reset
  canvas.py      PixelCanvas (QWidget): renders at zoom (1-64x int), lives in
                 a QScrollArea. Paint order: backdrop (checker or flat) ->
                 underlay photo -> sprite (nearest-neighbour, optional
                 display opacity) -> tool preview overlay -> grid lines
                 (BG_GRID mode and zoom >= 5). background_mode cycles
                 BG_GRID/BG_CHECKER/BG_PLAIN; preview_mode short-circuits
                 to flat backdrop + sprite only.
                 Routes mouse events to the current tool; Ctrl+wheel zoom
                 (cursor-anchored), middle-drag or space+drag pan
  tools.py       Pixel-exact primitives (Bresenham line, rect, sampled
                 ellipse, scanline flood fill, square brush stamp) + Tool
                 classes: Pencil, Eraser, Fill, Line, Rect, FilledRect,
                 Ellipse, FilledEllipse, Eyedropper, UnderlayEyedropper
  color_panel.py ColorPanel: primary/secondary swatches (left/right mouse),
                 QColorDialog wheel with alpha, hex field (#RGB/#RRGGBB/
                 #RRGGBBAA), generated 96-color ramp palette
                 (build_ramp_palette), 24 recent colors
  underlay.py    Underlay model (photo, opacity, scale, offset, visible;
                 coordinates in sprite-pixel space) + UnderlayPanel dock +
                 load_reference_image(): multi-format reference loader +
                 sample_pixel(): averaged photo color under a sprite pixel
  dialogs.py     NewSpriteDialog: arbitrary width x height, 1..4096
sprites/                     finished/in-progress sprite PNGs + their
                             .sprite.json sidecars (keep each pair together)
src_img/                     reference photos used as underlays
```

## Key design decisions

- **PNG as the canonical format** — chosen for Unity: lossless, full alpha,
  imports directly as a Sprite. Open any PNG to edit it at native dimensions.
- **Sidecar project file** — saving writes `<name>.sprite.json` next to the
  PNG containing the underlay setup (path/opacity/scale/offset/visible) so a
  trace-in-progress survives reopening. The sidecar is optional: bare PNGs
  open fine, a corrupt sidecar is ignored, and it is deleted on save if no
  photo is loaded. The underlay is display-only, never baked into the PNG.
- **Replace semantics, not blending** — all tools write the chosen RGBA value
  verbatim via `setPixelColor` (eraser writes transparent). This is what
  sprite artists expect; QPainter source-over blending is deliberately
  avoided for drawing operations.
- **Snapshot undo** — full-image copies per committed stroke (cheap at sprite
  sizes, cap 64). `push_undo()` is called at stroke start (press) for
  pencil/eraser and at commit (release) for shape tools.
- **Shape previews** — shape tools draw into `canvas.preview` (a transparent
  QImage the same size as the sprite) while dragging, then re-render the
  final shape directly onto the document on release. The preview is never
  composited into the document.
- **Zoom is integer-only** (1-64) with nearest-neighbour scaling to keep the
  pixel grid crisp. Grid lines only render at zoom >= 5 (GRID_MIN_ZOOM).
- **Checkerboard is locked to sprite pixels** — the transparency checker tile
  is rebuilt on every zoom change with cell size == zoom, so one checker
  square is exactly one sprite pixel and squares coincide with grid cells.
  (Originally a fixed 8-screen-px tile, which produced squares unrelated to
  pixel boundaries and made pixel edges ambiguous.) Grid line alpha is 110.
- **Background cycle vs. Preview are separate controls** — G cycles
  `canvas.background_mode` through grid+checker -> checker only -> plain
  (PLAIN_BG, neutral #606060) and back; the underlay stays visible in all
  three. Tab toggles `canvas.preview_mode`, which ignores background mode
  and draws only the sprite at full opacity over PLAIN_BG with no grid,
  checker, or photo -- what a game would render. Tools keep working in
  every mode. The current mode is shown in the status bar ("PREVIEW" wins).
  Tab is a window-wide shortcut, so it no longer moves keyboard focus
  between dock fields (Shift+Tab still does).
- **Hide Drawn Pixels (H)** is a third, independent display toggle
  (`canvas.sprite_hidden`, View > Hide Drawn Pixels). It skips drawing the
  document image in both normal and preview rendering, so you see only the
  backdrop/underlay; it never changes the document, background mode, or
  preview state. The shape-tool live preview overlay stays visible, and
  tools still edit (invisibly) while hidden. Status bar appends
  "PIXELS HIDDEN".
- **View toggles use plain letter keys (G, H), not Cmd+letter** — Cmd+H is
  reserved by macOS "Hide Application" and wins over the in-app shortcut
  (confirmed by the user on a real Mac), so Hide Drawn Pixels moved to H
  and the background cycle moved from Cmd+G to G to match. Like the tool
  keys, plain-letter shortcuts do not fire while typing in a text field
  (the hex input consumes them). Avoid Cmd+H / Cmd+M / Cmd+Q / Cmd+W for
  new shortcuts on macOS.
- **Sidecar underlay paths are absolute**, so moving a sprite PNG + its
  `.sprite.json` together (e.g. into `sprites/`) keeps the underlay restore
  working; moving the photo in `src_img/` would break it.
- **Underlay coordinates** are in sprite-pixel space (scale 1.0 = one photo
  pixel per sprite pixel); the canvas multiplies by zoom at render time.
  "Fit to Canvas" letterboxes and centers the photo.
- **Sprite opacity slider** (Trace Underlay dock) is display-only dimming of
  your own pixels so the photo shows through while tracing; it never affects
  saved output.
- **Underlay format support** — `load_reference_image()` in
  `sprite_drawer/underlay.py` handles: `.pdf` via QtPdf (first page rendered
  at up to 2048 px on the long side, PDF_MAX_RENDER_PX); anything QImage
  decodes natively (PNG, JPG/JPEG, BMP, GIF, WebP, TIFF); and a Pillow +
  pillow-heif fallback for `.heic`/`.heif` (and any other Pillow-readable
  format), with EXIF orientation applied so iPhone photos display upright.
  Failures return a null QImage; the panel shows a warning dialog. This
  loader is for the *underlay only* — sprites themselves still open/save as
  PNG.
- **Ramp palette is generated, not hard-coded** — `build_ramp_palette()` in
  `color_panel.py` produces a grays row plus 12 hue columns x 7 shades via
  `QColor.fromHslF` (constants PALETTE_HUES, PALETTE_SHADE_LIGHTNESS,
  PALETTE_SATURATION). Each column is a light-to-dark ramp of one hue, which
  is how pixel artists shade. Change the constants to resize the palette;
  swatches left-click to primary, right-click to secondary.
- **Underlay Pick samples an area, not a point** — `Underlay.sample_pixel()`
  maps the sprite pixel's footprint into photo space and averages every
  photo pixel it covers (subsampled to <= 32x32 taps for huge footprints).
  Because a sprite pixel typically covers many photo pixels (scale < 1), a
  point sample would pick up noise/grain; the average matches what the eye
  perceives under that grid cell. Returns None when the cell misses the
  photo, so the tool is a no-op there. It only sets the primary color; it
  never writes pixels (paint with the pencil afterward).

## Shortcuts

P pencil, E eraser, F fill, L line, R rect, Shift+R filled rect, O ellipse,
Shift+O filled ellipse, I eyedropper (sprite), U underlay pick (photo color
under the pixel), X swap colors, Ctrl+Z/Ctrl+Shift+Z
undo/redo, G cycle background (grid+checker / checker / plain),
Tab preview mode, H hide drawn pixels, Ctrl(+/-/0) zoom, Ctrl+wheel zoom, space/middle-drag
pan, Ctrl+R load reference photo, Ctrl+N/O/S/Shift+S file ops.

## Known limitations / future ideas

- No selection/move tool, no layers, no animation frames.
- Flood fill and filled shapes are Python-loop based; fine up to ~1024px
  sprites, would need numpy/bits() access for huge canvases.
- Eyedropper and Underlay Pick always set the primary color regardless of
  mouse button.
- No "trace brush" (paint pixels directly with the photo color beneath);
  Underlay Pick + pencil is the current workflow. Considered and deferred.
- Right-click paints with the secondary color (MS Paint behavior).
- No image resize/crop of an existing sprite (create new + redraw, or edit
  the PNG externally).

## Update log

- 2026-09-08: Initial construction. Full feature set described above
  implemented and verified end-to-end (new arbitrary-size sprite, all tools,
  hex colors, JPG underlay trace, PNG save/reopen with sidecar restore).
- 2026-09-08: Underlay format support extended to HEIC/HEIF (Pillow +
  pillow-heif, with EXIF orientation) and PDF (QtPdf first-page render,
  capped at 2048 px). New deps: Pillow, pillow-heif. File dialog filter
  updated. Smoke test now covers HEIC/PDF load and graceful rejection of
  unreadable files; verified against a real iPhone HEIC (src_img/).
- 2026-09-12: Palette expanded from 16 hard-coded colors to a generated
  96-color ramp palette (grays + 12 hues x 7 shades), right-click on a
  swatch sets secondary; recent colors widened to 24. Added the Underlay
  Pick tool (U): sets the primary color to the averaged photo color under
  the clicked sprite pixel via new `Underlay.sample_pixel()`. Smoke test
  gained 10 checks (sampling accuracy/averaging/out-of-bounds, palette size
  and distinctness, tool wiring and non-mutation).
- 2026-09-12: Checkerboard now one square per sprite pixel (tile rebuilt per
  zoom) instead of a fixed 8 px pattern; grid lines darkened (alpha 60 ->
  110). Smoke test checks the tile tracks zoom.
- 2026-09-13: "Show Grid" checkbox replaced by Ctrl+G background cycle
  (grid+checker -> checker only -> plain) and a new Tab Preview mode
  (sprite only over flat backdrop, hides grid/checker/underlay). Status bar
  shows the active mode. Motivation: with the pixel-aligned checkerboard,
  hiding grid lines alone left every pixel edge outlined, so there was no
  way to see just the drawn pixels. Smoke test now shows/activates the
  window and drives the real Ctrl+G and Tab shortcuts via QTest, plus
  pixel-checks the flat backdrop in plain and preview modes.
- 2026-09-23: Moved Damask_bass_sprite and TK_spr_v1 (PNG + .sprite.json)
  from the repo root into `sprites/`. Added Ctrl/Cmd+H "Hide Drawn Pixels"
  display toggle; Tab and Ctrl+G behavior unchanged. Smoke test gained 9
  checks (pixel hidden/shown by real shortcut, document untouched, other
  modes untouched, stays hidden in preview).
- 2026-09-23: Cmd+H triggered macOS "Hide Application" instead of the
  toggle, so Hide Drawn Pixels is now plain H, and at the user's request
  the background cycle moved from Cmd+G to plain G to match. Tab unchanged.
  Smoke test drives plain G/H, checks Ctrl+G no longer cycles, and checks
  typing g/h in the hex field doesn't trigger the toggles.
- 2026-09-23: Added end-user onboarding for non-technical Windows/macOS
  users: `README.md`, `CONTROLS.md`, `install_windows.bat`,
  `install_mac.command`, `run_windows.bat`, `run_mac.command`,
  `.gitattributes`. No app code changed. Mac installer verified end to end
  on a clean copy (fresh venv, packages, smoke test passes, app launches);
  Windows scripts are unverified on real Windows, but win_amd64 and
  win_arm64 wheels for every requirement on Python 3.14 were confirmed.
  Note: Qt has no Save As / Quit shortcut on Windows (menu only), so
  CONTROLS.md omits them.
- 2026-09-23: Moved the install/run scripts into `installation/` (README
  paths updated; scripts now `cd` to the parent folder). Added `.gitignore`
  (`.venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`) ahead of the first push
  to github.com/JohnRogan/sprite_drawer. The files were recreated rather
  than moved, so they are LF on disk and the `.command` files lost the
  execute bit; harmless, since README runs them via `bash` and
  `.gitattributes` makes Git check out `.bat` files as CRLF.

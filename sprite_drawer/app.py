"""MainWindow: menus, toolbar, docks, status bar, and file I/O.

File format: sprites save as PNG (Unity's best-supported sprite format,
lossless with full alpha). A `<name>.sprite.json` sidecar next to the PNG
persists the trace-underlay setup; opening a bare PNG works without it.
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QToolBar,
    QWidget,
)

from . import tools
from .canvas import BG_MODE_NAMES, PixelCanvas
from .color_panel import ColorPanel
from .dialogs import NewSpriteDialog
from .document import SpriteDocument
from .underlay import Underlay, UnderlayPanel


def sidecar_path(png_path: str) -> str:
    root, _ = os.path.splitext(png_path)
    return root + ".sprite.json"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc = SpriteDocument(32, 32)
        self.underlay = Underlay()
        self.canvas = PixelCanvas(self.doc, self.underlay)
        self.canvas.brush_size = 1

        # canvas inside a scroll area, centred
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidgetResizable(False)
        self.setCentralWidget(self.scroll)

        self._tools = {
            "pencil": tools.PencilTool(),
            "eraser": tools.EraserTool(),
            "fill": tools.FillTool(),
            "line": tools.LineTool(),
            "rect": tools.RectTool(),
            "frect": tools.FilledRectTool(),
            "ellipse": tools.EllipseTool(),
            "fellipse": tools.FilledEllipseTool(),
            "eyedropper": tools.EyedropperTool(),
            "underlay_pick": tools.UnderlayEyedropperTool(),
        }

        self._build_toolbar()
        self._build_docks()
        self._build_menus()
        self._build_statusbar()

        self.canvas.color_picked.connect(self.color_panel.set_primary)
        self.canvas.cursor_pixel_changed.connect(self._update_cursor_label)
        self.canvas.zoom_changed.connect(self._update_status)
        self.doc.modified_changed.connect(lambda _: self._update_title())
        self.doc.document_reset.connect(self._update_status)
        self.doc.changed.connect(self._update_undo_actions)

        self.canvas.current_tool = self._tools["pencil"]
        self.canvas.fit_zoom()
        self._update_title()
        self._update_status()
        self.resize(1200, 800)

    # ------------------------------------------------------------------ UI
    def _build_toolbar(self) -> None:
        tb = QToolBar("Tools")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
        group = QActionGroup(self)
        group.setExclusive(True)

        specs = [
            ("pencil", "Pencil", "P"),
            ("eraser", "Eraser", "E"),
            ("fill", "Fill", "F"),
            ("line", "Line", "L"),
            ("rect", "Rectangle", "R"),
            ("frect", "Filled Rect", "Shift+R"),
            ("ellipse", "Ellipse", "O"),
            ("fellipse", "Filled Ellipse", "Shift+O"),
            ("eyedropper", "Eyedropper", "I"),
            ("underlay_pick", "Underlay Pick", "U"),
        ]
        self._tool_actions: dict[str, QAction] = {}
        for key, label, shortcut in specs:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(f"{label} ({shortcut})")
            act.triggered.connect(
                lambda checked=False, k=key: self._select_tool(k))
            group.addAction(act)
            tb.addAction(act)
            self._tool_actions[key] = act
        self._tool_actions["pencil"].setChecked(True)

        tb.addSeparator()
        tb.addWidget(QLabel(" Size "))
        self.brush_spin = QSpinBox()
        self.brush_spin.setRange(1, 64)
        self.brush_spin.setValue(1)
        self.brush_spin.setToolTip("Brush size (pixels)")
        self.brush_spin.valueChanged.connect(
            lambda v: setattr(self.canvas, "brush_size", v))
        tb.addWidget(self.brush_spin)

    def _build_docks(self) -> None:
        self.color_panel = ColorPanel()
        self.color_panel.primary_changed.connect(
            lambda c: setattr(self.canvas, "primary_color", QColor(c)))
        self.color_panel.secondary_changed.connect(
            lambda c: setattr(self.canvas, "secondary_color", QColor(c)))
        color_dock = QDockWidget("Colors", self)
        color_dock.setWidget(self.color_panel)
        color_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, color_dock)

        self.underlay_panel = UnderlayPanel(self.underlay, self.canvas)
        underlay_dock = QDockWidget("Trace Underlay", self)
        underlay_dock.setWidget(self.underlay_panel)
        underlay_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, underlay_dock)

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        self._add_action(file_menu, "&New\u2026", QKeySequence.StandardKey.New,
                         self.action_new)
        self._add_action(file_menu, "&Open\u2026", QKeySequence.StandardKey.Open,
                         self.action_open)
        file_menu.addSeparator()
        self._add_action(file_menu, "&Save", QKeySequence.StandardKey.Save,
                         self.action_save)
        self._add_action(file_menu, "Save &As\u2026",
                         QKeySequence.StandardKey.SaveAs, self.action_save_as)
        file_menu.addSeparator()
        self._add_action(file_menu, "Load &Reference Photo\u2026", "Ctrl+R",
                         self.underlay_panel._load)
        file_menu.addSeparator()
        self._add_action(file_menu, "&Quit", QKeySequence.StandardKey.Quit,
                         self.close)

        edit_menu = mb.addMenu("&Edit")
        self.undo_action = self._add_action(
            edit_menu, "&Undo", QKeySequence.StandardKey.Undo, self.doc.undo)
        self.redo_action = self._add_action(
            edit_menu, "&Redo", QKeySequence.StandardKey.Redo, self.doc.redo)
        edit_menu.addSeparator()
        self._add_action(edit_menu, "&Clear Canvas", "Ctrl+Shift+K",
                         self.doc.clear)
        self._add_action(edit_menu, "Swap Colors", "X",
                         self.color_panel.swap_colors)

        view_menu = mb.addMenu("&View")
        self._add_action(view_menu, "Zoom &In", QKeySequence.StandardKey.ZoomIn,
                         self.canvas.zoom_in)
        self._add_action(view_menu, "Zoom &Out",
                         QKeySequence.StandardKey.ZoomOut, self.canvas.zoom_out)
        self._add_action(view_menu, "&Fit Zoom", "Ctrl+0", self.canvas.fit_zoom)
        view_menu.addSeparator()
        self._add_action(view_menu, "Cycle &Grid / Background", "G",
                         self._cycle_background)
        self.preview_action = QAction("&Preview Mode", self)
        self.preview_action.setCheckable(True)
        self.preview_action.setShortcut(QKeySequence(Qt.Key.Key_Tab))
        self.preview_action.setToolTip(
            "Show only the sprite over a flat background (Tab)")
        self.preview_action.toggled.connect(self._set_preview_mode)
        view_menu.addAction(self.preview_action)
        self.hide_pixels_action = QAction("&Hide Drawn Pixels", self)
        self.hide_pixels_action.setCheckable(True)
        # plain H: Cmd+H is claimed by macOS "Hide Application"
        self.hide_pixels_action.setShortcut(QKeySequence("H"))
        self.hide_pixels_action.setToolTip(
            "Temporarily hide your drawn pixels (H)")
        self.hide_pixels_action.toggled.connect(self._set_sprite_hidden)
        view_menu.addAction(self.hide_pixels_action)

    def _add_action(self, menu, text, shortcut, slot) -> QAction:
        act = QAction(text, self)
        if shortcut is not None:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    def _build_statusbar(self) -> None:
        self.pos_label = QLabel("")
        self.view_label = QLabel("")
        self.size_label = QLabel("")
        self.zoom_label = QLabel("")
        sb = self.statusBar()
        sb.addWidget(self.pos_label)
        sb.addPermanentWidget(self.view_label)
        sb.addPermanentWidget(self.size_label)
        sb.addPermanentWidget(self.zoom_label)
        self._update_view_label()

    # ------------------------------------------------------------- helpers
    def _select_tool(self, key: str) -> None:
        self.canvas.current_tool = self._tools[key]
        self.canvas.clear_preview()
        self.canvas.update()

    def _cycle_background(self) -> None:
        name = self.canvas.cycle_background()
        self.statusBar().showMessage(f"Background: {name}", 1500)
        self._update_view_label()

    def _set_preview_mode(self, on: bool) -> None:
        self.canvas.set_preview_mode(on)
        self._update_view_label()

    def _set_sprite_hidden(self, hidden: bool) -> None:
        self.canvas.set_sprite_hidden(hidden)
        self._update_view_label()

    def _update_view_label(self) -> None:
        if self.canvas.preview_mode:
            text = "PREVIEW"
        else:
            text = BG_MODE_NAMES[self.canvas.background_mode]
        if self.canvas.sprite_hidden:
            text += " | PIXELS HIDDEN"
        self.view_label.setText(f"{text}  ")

    def _update_cursor_label(self, x: int, y: int) -> None:
        if self.doc.in_bounds(x, y):
            self.pos_label.setText(f"({x}, {y})")
        else:
            self.pos_label.setText("")

    def _update_status(self) -> None:
        self.size_label.setText(f"{self.doc.width} x {self.doc.height} px  ")
        self.zoom_label.setText(f"zoom {self.canvas.zoom}x")
        self._update_title()
        self._update_undo_actions()

    def _update_undo_actions(self) -> None:
        self.undo_action.setEnabled(self.doc.can_undo)
        self.redo_action.setEnabled(self.doc.can_redo)

    def _update_title(self) -> None:
        name = (os.path.basename(self.doc.file_path)
                if self.doc.file_path else "untitled")
        star = "*" if self.doc.modified else ""
        self.setWindowTitle(f"{star}{name} - Sprite Drawer")

    def _confirm_discard(self) -> bool:
        """Return True if it is OK to discard the current document."""
        if not self.doc.modified:
            return True
        ret = QMessageBox.warning(
            self, "Unsaved changes",
            "The sprite has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if ret == QMessageBox.StandardButton.Save:
            return self.action_save()
        return ret == QMessageBox.StandardButton.Discard

    # ------------------------------------------------------------- file ops
    def action_new(self) -> None:
        if not self._confirm_discard():
            return
        dlg = NewSpriteDialog(self, self.doc.width, self.doc.height)
        if dlg.exec():
            w, h = dlg.sprite_size
            self.doc.new(w, h)
            self.underlay.clear()

    def action_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open sprite", "", "PNG images (*.png);;All files (*)")
        if not path:
            return
        if not self.doc.load(path):
            QMessageBox.warning(self, "Open failed",
                                f"Could not open:\n{path}")
            return
        # restore underlay from sidecar if present
        self.underlay.clear()
        sc = sidecar_path(path)
        if os.path.exists(sc):
            try:
                with open(sc, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.underlay.from_dict(data.get("underlay", {}))
            except (OSError, json.JSONDecodeError, ValueError):
                pass  # sidecar is optional; a bad one should never block open
        self._update_status()

    def action_save(self) -> bool:
        if self.doc.file_path is None:
            return self.action_save_as()
        return self._save_to(self.doc.file_path)

    def action_save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save sprite", self.doc.file_path or "sprite.png",
            "PNG images (*.png)")
        if not path:
            return False
        if not path.lower().endswith(".png"):
            path += ".png"
        return self._save_to(path)

    def _save_to(self, path: str) -> bool:
        if not self.doc.save(path):
            QMessageBox.warning(self, "Save failed",
                                f"Could not save:\n{path}")
            return False
        # persist underlay setup in the sidecar (only when a photo is loaded)
        sc = sidecar_path(path)
        try:
            if self.underlay.loaded:
                with open(sc, "w", encoding="utf-8") as f:
                    json.dump({"underlay": self.underlay.to_dict()}, f, indent=2)
            elif os.path.exists(sc):
                os.remove(sc)
        except OSError:
            pass  # sidecar failure should not fail the save
        self._update_title()
        return True

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

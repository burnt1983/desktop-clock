#!/usr/bin/env python3
"""Transparent Linux desktop clock — custom face image, analog + digital.

No window frame. PNG/SVG faces keep their alpha. Right-click for options.
Works as a desklet (--desklet, default) or a compact panel chip (--panel).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import cairo

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import linux_widget as lw
except ImportError:
    lw = None

HOME = Path.home()
CFG_DIR = HOME / ".config" / "linux-desktop-clock"
CFG = CFG_DIR / "config.json"
FACE_COPY = CFG_DIR / "face.png"
APP_ID = "io.github.burnt1983.desktopclock"
PRGNAME = "desktop-clock"

DEFAULTS = {
    "size": 220,
    "x": None,
    "y": None,
    "seconds": True,
    "digital": True,
    "hour24": False,
    "transparent": True,
    "ticks": True,
    "keep_above": True,
    "face": "",
    "digital_below": True,
    "panel": False,
}


def load_cfg() -> dict:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    data = dict(DEFAULTS)
    if CFG.exists():
        try:
            loaded = json.loads(CFG.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save_cfg(data: dict) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CFG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CFG)


def load_face(path: str, size: int) -> GdkPixbuf.Pixbuf | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_size(str(p), size, size)
    except Exception:
        return None


class ClockFace(Gtk.DrawingArea):
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.face = None
        self._reload_face()
        self.set_size_request(cfg["size"], cfg["size"])
        self.connect("draw", self.on_draw)

    def _reload_face(self) -> None:
        size = int(self.cfg.get("size") or 220)
        self.face = load_face(str(self.cfg.get("face") or ""), size)

    def set_size_px(self, size: int) -> None:
        self.cfg["size"] = int(size)
        self.set_size_request(size, size)
        self._reload_face()
        self.queue_draw()

    def on_draw(self, _w, cr) -> bool:
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        size = min(w, h)
        cx, cy = w / 2.0, h / 2.0
        r = size / 2.0 - 2

        if self.cfg.get("transparent"):
            cr.set_operator(cairo.OPERATOR_CLEAR)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
        else:
            cr.set_source_rgb(0.08, 0.08, 0.10)
            cr.paint()

        cr.save()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.clip()
        if self.face is not None:
            pw, ph = self.face.get_width(), self.face.get_height()
            cr.save()
            cr.translate(cx - pw / 2, cy - ph / 2)
            Gdk.cairo_set_source_pixbuf(cr, self.face, 0, 0)
            cr.paint()
            cr.restore()
        else:
            # Default face: faint ring, no filled plate (stays transparent)
            cr.set_source_rgba(1, 1, 1, 0.22)
            cr.set_line_width(max(2.0, r * 0.03))
            cr.arc(cx, cy, r * 0.98, 0, 2 * math.pi)
            cr.stroke()
        cr.restore()

        if self.cfg.get("ticks"):
            cr.set_source_rgba(1, 1, 1, 0.85 if self.face is None else 0.55)
            for i in range(60):
                ang = math.radians(i * 6 - 90)
                inner = r * (0.88 if i % 5 == 0 else 0.93)
                outer = r * 0.97
                cr.set_line_width(2.2 if i % 5 == 0 else 1.0)
                cr.move_to(cx + inner * math.cos(ang), cy + inner * math.sin(ang))
                cr.line_to(cx + outer * math.cos(ang), cy + outer * math.sin(ang))
                cr.stroke()

        now = time.localtime()
        sec = now.tm_sec + time.time() % 1
        minute = now.tm_min + sec / 60.0
        hour = (now.tm_hour % 12) + minute / 60.0

        def hand(frac, length, width, rgba):
            ang = math.radians(frac * 360 - 90)
            cr.set_source_rgba(*rgba)
            cr.set_line_width(width)
            cr.set_line_cap(1)
            cr.move_to(cx, cy)
            cr.line_to(cx + length * math.cos(ang), cy + length * math.sin(ang))
            cr.stroke()

        hand(hour / 12.0, r * 0.52, max(3.5, r * 0.045), (1, 1, 1, 0.95))
        hand(minute / 60.0, r * 0.78, max(2.4, r * 0.03), (1, 1, 1, 0.95))
        if self.cfg.get("seconds"):
            hand(sec / 60.0, r * 0.86, max(1.2, r * 0.015), (0.95, 0.25, 0.22, 0.95))

        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.arc(cx, cy, max(3.0, r * 0.04), 0, 2 * math.pi)
        cr.fill()
        return True


class ClockWindow(Gtk.Window):
    def __init__(self, panel: bool = False):
        super().__init__(title="Desktop Clock")
        self.cfg = load_cfg()
        if panel:
            self.cfg["panel"] = True
            if self.cfg.get("size", 220) > 96:
                self.cfg["size"] = 72
            self.cfg["digital"] = True
        self.panel = panel

        if lw:
            lw.apply_rgba(self)
            if panel:
                lw.apply_panel(self)
            else:
                lw.apply_desklet(self, decorated=False, keep_above=bool(self.cfg.get("keep_above", True)))
        else:
            self.set_decorated(False)
            self.set_skip_taskbar_hint(True)
            self.set_keep_above(True)

        if self.cfg.get("transparent", True):
            if lw:
                lw.apply_rgba(self)
            css = b"""
            window, window.background { background-color: transparent; }
            label.digital { color: #ffffff; font-weight: 600; font-size: 16px; }
            """
        else:
            css = b"""
            window { background-color: #141416; }
            label.digital { color: #ffffff; font-weight: 600; font-size: 16px; }
            """
        if lw:
            lw.load_css(css)
        else:
            p = Gtk.CssProvider()
            p.load_from_data(css)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.face = ClockFace(self.cfg)
        self.digital = Gtk.Label(label="")
        self.digital.get_style_context().add_class("digital")
        self.digital.set_halign(Gtk.Align.CENTER)
        self.box.pack_start(self.face, True, True, 0)
        self.box.pack_start(self.digital, False, False, 0)
        self.add(self.box)

        if lw:
            lw.enable_drag_move(self, self.face)
        self.connect("button-press-event", self.on_click)
        self.face.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK
        )
        self.face.connect("scroll-event", self.on_scroll)
        self.connect("configure-event", self.on_configure)
        self.connect("delete-event", self.on_delete)

        x, y = self.cfg.get("x"), self.cfg.get("y")
        if isinstance(x, int) and isinstance(y, int) and x >= 0 and y >= 0:
            self.move(x, y)

        self._tick()
        GLib.timeout_add(200 if self.cfg.get("seconds") else 1000, self._tick)

    def _tick(self) -> bool:
        now = time.localtime()
        if self.cfg.get("hour24"):
            stamp = time.strftime("%H:%M:%S" if self.cfg.get("seconds") else "%H:%M", now)
        else:
            stamp = time.strftime("%I:%M:%S %p" if self.cfg.get("seconds") else "%I:%M %p", now).lstrip("0")
        self.digital.set_text(stamp)
        self.digital.set_visible(bool(self.cfg.get("digital")))
        self.face.queue_draw()
        return True

    def on_click(self, _w, event) -> bool:
        if event.button == 3:
            self._menu(event)
            return True
        return False

    def _resize(self, delta: int) -> None:
        size = int(self.cfg.get("size") or 220)
        size = max(64, min(640, size + delta))
        self.face.set_size_px(size)
        save_cfg(self.cfg)

    def on_scroll(self, _w, event) -> bool:
        if event.direction == Gdk.ScrollDirection.UP:
            self._resize(16)
            return True
        if event.direction == Gdk.ScrollDirection.DOWN:
            self._resize(-16)
            return True
        return False

    def on_configure(self, _w, event) -> bool:
        self.cfg["x"] = int(event.x)
        self.cfg["y"] = int(event.y)
        return False

    def on_delete(self, *_a) -> bool:
        save_cfg(self.cfg)
        return False

    def _toggle(self, key: str) -> None:
        self.cfg[key] = not bool(self.cfg.get(key))
        if key == "transparent":
            # Re-apply CSS by restarting is cleaner; toggle class here.
            pass
        if key == "keep_above":
            self.set_keep_above(bool(self.cfg[key]))
        self.face._reload_face()
        self.face.queue_draw()
        self._tick()
        save_cfg(self.cfg)

    def _choose_face(self) -> None:
        dlg = Gtk.FileChooserDialog(
            title="Clock face image (PNG with transparency works best)",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Use this image", Gtk.ResponseType.OK)
        filt = Gtk.FileFilter()
        filt.set_name("Images")
        for pat in ("*.png", "*.svg", "*.jpg", "*.jpeg", "*.webp"):
            filt.add_pattern(pat)
        dlg.add_filter(filt)
        resp = dlg.run()
        path = dlg.get_filename() if resp == Gtk.ResponseType.OK else None
        dlg.destroy()
        if not path:
            return
        try:
            CFG_DIR.mkdir(parents=True, exist_ok=True)
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
            pb.savev(str(FACE_COPY), "png", [], [])
            self.cfg["face"] = str(FACE_COPY)
        except Exception:
            self.cfg["face"] = path
        self.face._reload_face()
        self.face.queue_draw()
        save_cfg(self.cfg)

    def _clear_face(self) -> None:
        self.cfg["face"] = ""
        self.face._reload_face()
        self.face.queue_draw()
        save_cfg(self.cfg)

    def _menu(self, event) -> None:
        menu = Gtk.Menu()

        def item(label, fn):
            it = Gtk.MenuItem(label=label)
            it.connect("activate", lambda *_: fn())
            menu.append(it)

        def check(label, key):
            it = Gtk.CheckMenuItem(label=label)
            it.set_active(bool(self.cfg.get(key)))
            it.connect("toggled", lambda *_: self._toggle(key))
            menu.append(it)

        check("Second hand", "seconds")
        check("Digital time underneath", "digital")
        check("24-hour digital", "hour24")
        check("Tick marks", "ticks")
        check("Transparent background (no frame)", "transparent")
        check("Keep on top", "keep_above")
        menu.append(Gtk.SeparatorMenuItem())
        item("Choose face image / logo…", self._choose_face)
        item("Clear face (ticks only)", self._clear_face)
        menu.append(Gtk.SeparatorMenuItem())
        item("Larger  (or scroll up)", lambda: self._resize(16))
        item("Smaller (or scroll down)", lambda: self._resize(-16))
        menu.append(Gtk.SeparatorMenuItem())
        item("Quit", Gtk.main_quit)
        menu.show_all()
        menu.popup_at_pointer(event)


def main() -> int:
    GLib.set_prgname(PRGNAME)
    panel = "--panel" in sys.argv
    win = ClockWindow(panel=panel)
    win.show_all()
    if not win.cfg.get("digital"):
        win.digital.hide()
    Gtk.main()
    save_cfg(win.cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())

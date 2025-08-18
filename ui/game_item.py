# ui/game_item.py
"""
GameItem widget (grid tile or list row).
Robust to differences in Qt bindings / static analyzers:
 - QCoreApplication imported from QtCore (fixes ImportError)
 - Play button uses objectName/role so global theme controls color
 - Heart button visuals update when favorites change
"""

import os
import re
import requests
from pathlib import Path
from typing import Optional, Any

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSizePolicy
)
from PySide6.QtGui import QPixmap, QIcon, QPalette
from PySide6.QtCore import Qt, QSize, QCoreApplication   # <-- QCoreApplication belongs here

from common.favorites import add_favorite, remove_favorite, is_favorite

# Cache directory for downloaded covers
CACHE_DIR = Path.home() / ".cache" / "mystical" / "covers"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Display caps
MAX_COVER_W = 420
MAX_COVER_H = 620

# Thumbnail size for list mode
LIST_THUMB_W = 64
LIST_THUMB_H = 64

# IGDB preferred sizes (try bigger first)
IGDB_SIZES = ("t_720p", "t_cover_big", "t_cover_med", "t_cover_small", "t_thumb")


# ---------------------------
# Helpers (robust to stubs)
# ---------------------------
def _is_light_theme() -> bool:
    """
    Detect whether the application's palette is light.
    Uses safe fallbacks so static analyzers don't complain.
    """
    app = QCoreApplication.instance()
    if not app:
        return True  # default to light for editing/testing

    try:
        pal = app.palette()
        # Common style: pal.color(QPalette.Window)
        win_color = pal.color(QPalette.Window)
        text_color = pal.color(QPalette.WindowText)
        return win_color.lightness() > text_color.lightness()
    except Exception:
        # Fallback for differing stubs / Qt versions
        try:
            win_color = pal.color(QPalette.ColorRole.Window)  # alternate enum access
            text_color = pal.color(QPalette.ColorRole.WindowText)
            return win_color.lightness() > text_color.lightness()
        except Exception:
            # Give up, assume dark to avoid bright text on dark backgrounds
            return False


def _theme_colors() -> dict:
    """
    Small palette for widget-level styling depending on theme.
    """
    if _is_light_theme():
        return {
            "cover_bg": "#f5f5f5",
            "thumb_bg": "#efefef",
            "text": "#111111",
            "meta": "#5f6368",
            "play_bg": "#e8f0fe",
            "play_hover": "#d2e3fc",
            "play_text": "#1a73e8",
            "overlay_bg": "rgba(255,255,255,0.85)",
            "heart_overlay": "rgba(0,0,0,0.08)",
        }
    else:
        return {
            "cover_bg": "#1f2224",
            "thumb_bg": "#2b2b2b",
            "text": "#e8eaed",
            "meta": "#9aa0a6",
            "play_bg": "#1f78d1",
            "play_hover": "#1766a8",
            "play_text": "#ffffff",
            "overlay_bg": "rgba(0,0,0,0.36)",
            "heart_overlay": "rgba(255,255,255,0.04)",
        }


def _safe_ident(name: str) -> str:
    """Return a filesystem safe id for caching."""
    if not name:
        return "unknown"
    s = str(name)
    s = re.sub(r"[^\w\-_\. ]+", "", s)
    s = s.strip().replace(" ", "_")
    return s[:200]


def _normalize_igdb_url(url: str, preferred_size: str) -> str:
    """Convert IGDB protocol-relative URLs and replace size token with preferred size."""
    if not url:
        return url
    u = url.strip()
    if u.startswith("//"):
        u = "https://" + u.lstrip("/")
    parts = u.split("/")
    for i, p in enumerate(parts):
        if p.startswith("t_"):
            parts[i] = preferred_size
            break
    return "/".join(parts)


def _download_cover(url: str, filename: Path) -> Optional[Path]:
    """Download a remote URL into filename (returns Path on success)."""
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        with open(filename, "wb") as fh:
            fh.write(r.content)
        return filename
    except Exception:
        try:
            if filename.exists():
                filename.unlink()
        except Exception:
            pass
        return None


def get_cached_cover_path(game: Any) -> Optional[str]:
    """
    Resolve a local cover path:
      1) prefer game.image_path or game.cover_path if exists
      2) try to download using game.cover_url (IGDB url) trying multiple sizes
    Returns path string or None.
    """
    for attr in ("image_path", "cover_path"):
        val = getattr(game, attr, None)
        if val:
            try:
                p = Path(val)
                if p.exists():
                    return str(p)
            except Exception:
                try:
                    if Path(str(val)).exists():
                        return str(val)
                except Exception:
                    pass

    remote = getattr(game, "cover_url", None)
    if not remote:
        return None

    ident = _safe_ident(getattr(game, "id", None) or getattr(game, "name", None) or str(abs(hash(game))))
    local = CACHE_DIR / f"{ident}.jpg"
    if local.exists():
        return str(local)

    # try preferred sizes
    for size in IGDB_SIZES:
        url = _normalize_igdb_url(str(remote), preferred_size=size)
        res = _download_cover(url, local)
        if res:
            return str(res)
    return None


# ---------------------------
# Widget
# ---------------------------
class GameItemWidget(QWidget):
    def __init__(self, game: Any, grid_mode: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("gameItem")

        self.game = game
        self.grid_mode = bool(grid_mode)
        self.colors = _theme_colors()

        # icon assets directory
        asset_dir = Path("assets") / "icons"
        self.heart_filled_red = asset_dir / "heart_filled_red.png"
        self.heart_filled = asset_dir / "heart_filled.png"
        self.heart_outline_light = asset_dir / "heart_dark.png"
        self.heart_outline = asset_dir / "heart.png"

        # choose icons safely
        self._outline_icon_path = None
        if _is_light_theme() and self.heart_outline_light.exists():
            self._outline_icon_path = str(self.heart_outline_light)
        elif self.heart_outline.exists():
            self._outline_icon_path = str(self.heart_outline)

        if self.heart_filled_red.exists():
            self._filled_icon_path = str(self.heart_filled_red)
        elif self.heart_filled.exists():
            self._filled_icon_path = str(self.heart_filled)
        else:
            self._filled_icon_path = None

        # Build UI
        if self.grid_mode:
            self._build_grid_ui()
        else:
            self._build_list_ui()

        # Ensure heart visual initial state is correct
        self._update_heart_visual()

    # ---- Grid UI ----
    def _build_grid_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(6)

        # cover label (keeps natural pixmap size when possible)
        self.cover_label = QLabel()
        self.cover_label.setAlignment(getattr(Qt, "AlignCenter", Qt.AlignmentFlag.AlignCenter))
        self.cover_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cover_label.setStyleSheet(f"border-radius:6px; background-color: {self.colors['cover_bg']};")

        cover_local = get_cached_cover_path(self.game)
        if cover_local and Path(cover_local).exists():
            pix = QPixmap(cover_local)
            if not pix.isNull():
                pw, ph = pix.width(), pix.height()
                if pw <= MAX_COVER_W and ph <= MAX_COVER_H:
                    display = pix
                else:
                    keep = getattr(Qt, "KeepAspectRatio", Qt.KeepAspectRatio)
                    smooth = getattr(Qt, "SmoothTransformation", Qt.SmoothTransformation)
                    display = pix.scaled(MAX_COVER_W, MAX_COVER_H, keep, smooth)
                self.cover_label.setPixmap(display)
                self.cover_label.setFixedSize(display.width(), display.height())
            else:
                self.cover_label.setText(self.game.name or "No Cover")
                self.cover_label.setFixedSize(MAX_COVER_W // 2, MAX_COVER_H // 3)
        else:
            self.cover_label.setText(self.game.name or "No Cover")
            self.cover_label.setWordWrap(True)
            self.cover_label.setFixedSize(MAX_COVER_W // 2, MAX_COVER_H // 3)

        main.addWidget(self.cover_label, alignment=getattr(Qt, "AlignCenter", Qt.AlignmentFlag.AlignCenter))

        # heart (floating, parented to cover_label)
        self.heart_btn = QPushButton(self.cover_label)
        self.heart_btn.setCheckable(True)
        self.heart_btn.setFixedSize(28, 28)
        self.heart_btn.setStyleSheet(f"border:none; background-color: {self.colors.get('heart_overlay','rgba(0,0,0,0.16)')}; border-radius:12px;")
        self.heart_btn.clicked.connect(self._on_heart_clicked)

        # title
        text_color = self.colors.get("text", "#000000")
        self.name_label = QLabel(self.game.name or "Unknown")
        self.name_label.setAlignment(getattr(Qt, "AlignCenter", Qt.AlignmentFlag.AlignCenter))
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet(f"background: transparent; font-weight:600; margin-top:4px; margin-bottom:4px; color: {text_color};")
        main.addWidget(self.name_label)

        # Play button: DO NOT set color-level stylesheet here.
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setProperty("role", "primary")
        self.play_button.setFixedHeight(34)
        main.addWidget(self.play_button)

        # position overlays now (resizeEvent will keep them correct)
        self._reposition_overlays()

    # ---- List UI ----
    def _build_list_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(8)

        self.thumb = QLabel()
        self.thumb.setFixedSize(LIST_THUMB_W, LIST_THUMB_H)
        self.thumb.setAlignment(getattr(Qt, "AlignCenter", Qt.AlignmentFlag.AlignCenter))
        self.thumb.setStyleSheet(f"background-color: {self.colors['thumb_bg']}; border-radius:6px;")

        cover_local = get_cached_cover_path(self.game)
        if cover_local and Path(cover_local).exists():
            pix = QPixmap(cover_local)
            if not pix.isNull():
                keep = getattr(Qt, "KeepAspectRatio", Qt.KeepAspectRatio)
                smooth = getattr(Qt, "SmoothTransformation", Qt.SmoothTransformation)
                display = pix.scaled(LIST_THUMB_W, LIST_THUMB_H, keep, smooth)
                self.thumb.setPixmap(display)
            else:
                self.thumb.setText("No\nCover")
        else:
            self.thumb.setText("No\nCover")

        main.addWidget(self.thumb)

        v = QVBoxLayout()
        v.setSpacing(2)
        text_color = self.colors.get("text", "#000")
        self.name_label = QLabel(self.game.name or "Unknown")
        self.name_label.setStyleSheet(f"background: transparent; font-weight:600; margin-top:2px; margin-bottom:2px; color: {text_color};")
        v.addWidget(self.name_label)

        meta = []
        plat = getattr(self.game, "platform", None)
        if plat:
            plat_val = getattr(plat, "value", str(plat))
            meta.append(plat_val)
        if getattr(self.game, "installed", False):
            meta.append("Installed")
        meta_label = QLabel(" • ".join(meta))
        meta_label.setStyleSheet(f"color: {self.colors.get('meta','#888')}; font-size:12px; background: transparent;")
        v.addWidget(meta_label)
        main.addLayout(v)
        main.addStretch()

        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setProperty("role", "primary")
        self.play_button.setFixedHeight(28)
        main.addWidget(self.play_button)

        self.heart_btn = QPushButton()
        self.heart_btn.setCheckable(True)
        self.heart_btn.setFixedSize(26, 26)
        self.heart_btn.setStyleSheet("border:none; background:transparent;")
        self.heart_btn.clicked.connect(self._on_heart_clicked)
        main.addWidget(self.heart_btn)

    # -------------------
    # overlay positioning
    # -------------------
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._reposition_overlays()

    def _reposition_overlays(self):
        if self.grid_mode and hasattr(self, "cover_label") and hasattr(self, "heart_btn"):
            try:
                cw = self.cover_label.width()
                x = cw - self.heart_btn.width() - 8
                y = 8
                self.heart_btn.move(x, y)
            except Exception:
                pass

    # -------------------
    # favorites visuals / toggling
    # -------------------
    def _update_heart_visual(self):
        # use str keys so type checkers are happy
        key = str(getattr(self.game, "id", None) or getattr(self.game, "name", ""))
        fav = False
        try:
            fav = bool(is_favorite(key))
        except Exception:
            try:
                fav = bool(is_favorite(str(getattr(self.game, "name", ""))))
            except Exception:
                fav = False

        if fav:
            if self._filled_icon_path:
                self.heart_btn.setIcon(QIcon(self._filled_icon_path))
                self.heart_btn.setIconSize(QSize(18, 18))
                self.heart_btn.setStyleSheet("border:none; background-color: rgba(0,0,0,0.28); border-radius:12px;")
            else:
                if self._outline_icon_path:
                    self.heart_btn.setIcon(QIcon(self._outline_icon_path))
                    self.heart_btn.setIconSize(QSize(18, 18))
                self.heart_btn.setStyleSheet("border:none; background-color: rgba(220, 20, 60, 0.95); border-radius:12px;")
            self.heart_btn.setChecked(True)
        else:
            if self._outline_icon_path:
                self.heart_btn.setIcon(QIcon(self._outline_icon_path))
                self.heart_btn.setIconSize(QSize(18, 18))
            self.heart_btn.setStyleSheet(f"border:none; background-color: {self.colors.get('heart_overlay','rgba(0,0,0,0.16)')}; border-radius:12px;")
            self.heart_btn.setChecked(False)

    def _on_heart_clicked(self):
        key = str(getattr(self.game, "id", None) or getattr(self.game, "name", ""))
        try:
            if is_favorite(key):
                remove_favorite(key)
            else:
                add_favorite(key)
        except Exception:
            try:
                name = str(getattr(self.game, "name", ""))
                if is_favorite(name):
                    remove_favorite(name)
                else:
                    add_favorite(name)
            except Exception:
                pass

        # refresh icon immediately
        self._update_heart_visual()

# ui/game_item.py
import os
import re
import requests
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSizePolicy
)
from PySide6.QtGui import QPixmap, QIcon, QPalette
from PySide6.QtCore import Qt, QSize, QCoreApplication

from common.favorites import add_favorite, remove_favorite, is_favorite

CACHE_DIR = Path.home() / ".cache" / "mystical" / "covers"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_COVER_W = 420
MAX_COVER_H = 620
LIST_THUMB_W = 64
LIST_THUMB_H = 64
IGDB_SIZES = ("t_720p", "t_cover_big", "t_cover_med", "t_cover_small", "t_thumb")


def _is_light_theme() -> bool:
    app = QCoreApplication.instance()
    if not app:
        return False
    try:
        pal: QPalette = app.palette()
        return pal.color(QPalette.Window).lightness() > pal.color(QPalette.WindowText).lightness()
    except Exception:
        return True


def _theme_colors() -> dict:
    if _is_light_theme():
        return {
            "cover_bg": "#f5f5f5",
            "thumb_bg": "#efefef",
            "meta": "#5f6368",
            "play_bg": "#e8f0fe",
            "play_hover": "#d2e3fc",
            "play_text": "#1a73e8",
            "overlay_bg": "rgba(255,255,255,0.85)",
        }
    else:
        return {
            "cover_bg": "#2a2a2a",
            "thumb_bg": "#2b2b2b",
            "meta": "#9aa0a6",
            "play_bg": "#1f78d1",
            "play_hover": "#1766a8",
            "play_text": "white",
            "overlay_bg": "rgba(0,0,0,0.36)",
        }


def _safe_ident(name: str) -> str:
    if not name:
        return "unknown"
    s = str(name)
    s = re.sub(r"[^\w\-_\. ]+", "", s)
    s = s.strip().replace(" ", "_")
    return s[:200]


def _normalize_igdb_url(url: str, preferred_size: str) -> str:
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


def get_cached_cover_path(game) -> Optional[str]:
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

    for size in IGDB_SIZES:
        url = _normalize_igdb_url(str(remote), preferred_size=size)
        res = _download_cover(url, local)
        if res:
            return str(res)

    return None


class GameItemWidget(QWidget):
    def __init__(self, game, grid_mode: bool = False, parent=None):
        super().__init__(parent)
        # allow stylesheet targeting
        self.setObjectName("gameItem")

        self.game = game
        self.grid_mode = bool(grid_mode)
        self.colors = _theme_colors()

        # icon candidates
        self.asset_dir = Path("assets") / "icons"
        # filled heart (preferred red filled)
        self.heart_filled_red = self.asset_dir / "heart_filled_red.png"
        self.heart_filled = self.asset_dir / "heart_filled.png"
        # outline variants: one for light theme (dark outline) and default white outline
        self.heart_outline_light = self.asset_dir / "heart_dark.png"
        self.heart_outline = self.asset_dir / "heart.png"

        # pick outline based on theme
        outline_icon = str(self.heart_outline_light) if _is_light_theme() and self.heart_outline_light.exists() else str(self.heart_outline) if self.heart_outline.exists() else None
        self._outline_icon_path = outline_icon

        # pick filled icon (prefer explicit red)
        if self.heart_filled_red.exists():
            self._filled_icon_path = str(self.heart_filled_red)
        elif self.heart_filled.exists():
            self._filled_icon_path = str(self.heart_filled)
        else:
            self._filled_icon_path = None

        if self.grid_mode:
            self._build_grid_ui()
        else:
            self._build_list_ui()

        # ensure the heart icon initial state reflects favorites backend
        self._update_heart_visual()

    # ---------- UI builders ----------
    def _build_grid_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(6)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignCenter)
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
                    display = pix.scaled(MAX_COVER_W, MAX_COVER_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.cover_label.setPixmap(display)
                self.cover_label.setFixedSize(display.width(), display.height())
            else:
                self.cover_label.setText(self.game.name or "No Cover")
                self.cover_label.setFixedSize(MAX_COVER_W // 2, MAX_COVER_H // 3)
        else:
            self.cover_label.setText(self.game.name or "No Cover")
            self.cover_label.setWordWrap(True)
            self.cover_label.setFixedSize(MAX_COVER_W // 2, MAX_COVER_H // 3)

        main.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        # heart button placed on cover_label
        self.heart_btn = QPushButton(self.cover_label)
        self.heart_btn.setCheckable(True)
        self.heart_btn.setFixedSize(28, 28)
        self.heart_btn.setStyleSheet(f"border:none; background-color:{self.colors['overlay_bg']}; border-radius:12px;")
        self.heart_btn.clicked.connect(self._on_heart_clicked)

        # title
        self.name_label = QLabel(self.game.name or "Unknown")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-weight:600; margin-top:4px; margin-bottom:4px;")
        main.addWidget(self.name_label)

        # play button (theme controls appearance)
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setProperty("role", "primary")
        self.play_button.setFixedHeight(34)
        main.addWidget(self.play_button)

        self._reposition_overlays()

    def _build_list_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(8)

        self.thumb = QLabel()
        self.thumb.setFixedSize(LIST_THUMB_W, LIST_THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet(f"background-color: {self.colors['thumb_bg']}; border-radius:6px;")

        cover_local = get_cached_cover_path(self.game)
        if cover_local and Path(cover_local).exists():
            pix = QPixmap(cover_local)
            if not pix.isNull():
                display = pix.scaled(LIST_THUMB_W, LIST_THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb.setPixmap(display)
            else:
                self.thumb.setText("No\nCover")
        else:
            self.thumb.setText("No\nCover")

        main.addWidget(self.thumb)

        v = QVBoxLayout()
        v.setSpacing(2)
        self.name_label = QLabel(self.game.name or "Unknown")
        self.name_label.setStyleSheet("font-weight:600; margin-top:2px; margin-bottom:2px;")
        v.addWidget(self.name_label)

        meta = []
        plat = getattr(self.game, "platform", None)
        if plat:
            plat_val = getattr(plat, "value", str(plat))
            meta.append(plat_val)
        if getattr(self.game, "installed", False):
            meta.append("Installed")
        meta_label = QLabel(" • ".join(meta))
        meta_label.setStyleSheet("font-size:12px;")
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

    # repositioning overlay heart on cover
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

    # Update heart icon/appearance according to favorites backend
    def _update_heart_visual(self):
        fav = False
        try:
            fav = is_favorite(self.game.id)
        except Exception:
            # if backend uses name instead of id, try name
            try:
                fav = is_favorite(getattr(self.game, "name", ""))
            except Exception:
                fav = False

        # choose icon for checked vs unchecked
        if fav:
            # prefer explicit filled red icon
            if self._filled_icon_path:
                self.heart_btn.setIcon(QIcon(self._filled_icon_path))
                self.heart_btn.setIconSize(QSize(18, 18))
                # keep neutral circular overlay so the red icon pops
                self.heart_btn.setStyleSheet("border:none; background-color: rgba(0,0,0,0.32); border-radius:12px;")
            else:
                # fallback: use outline icon and tint the button background red
                if self._outline_icon_path:
                    self.heart_btn.setIcon(QIcon(self._outline_icon_path))
                    self.heart_btn.setIconSize(QSize(18, 18))
                # red circular background
                self.heart_btn.setStyleSheet("border:none; background-color: rgba(220, 20, 60, 0.95); border-radius:12px;")
            self.heart_btn.setChecked(True)
        else:
            # not favored: outline icon and neutral overlay
            if self._outline_icon_path:
                self.heart_btn.setIcon(QIcon(self._outline_icon_path))
                self.heart_btn.setIconSize(QSize(18, 18))
            self.heart_btn.setStyleSheet("border:none; background-color: rgba(0,0,0,0.16); border-radius:12px;")
            self.heart_btn.setChecked(False)

    # toggle favorites and update visuals
    def _on_heart_clicked(self):
        try:
            # Use id first; fallback to name
            key = getattr(self.game, "id", None) or getattr(self.game, "name", None)
            if is_favorite(key):
                remove_favorite(key)
            else:
                add_favorite(key)
        except Exception:
            # best effort fallback: toggle by name
            try:
                name = getattr(self.game, "name", "")
                if is_favorite(name):
                    remove_favorite(name)
                else:
                    add_favorite(name)
            except Exception:
                pass

        # update the icon immediately
        self._update_heart_visual()

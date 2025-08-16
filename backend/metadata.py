# backend/metadata.py
"""
Metadata helper module for fetching game covers, descriptions, etc.
Uses IGDB API with automatic OAuth token refresh and writes local cover files
to assets/covers/<platform>/<safe_game_name>.jpg

When a cover is found it sets these attributes on the GameEntry:
 - game.cover_path -> local Path (str or Path)
 - game.cover_url  -> remote URL returned by IGDB
 - game.image_path -> alias for cover_path (some parts of UI use this)
"""

from pathlib import Path
from backend.models import GameEntry
from common.utils import log_info, log_error
from common.settings import load_config, save_config
import os
import requests
import time
import re

IGDB_API_URL = "https://api.igdb.com/v4/games"
COVERS_API_URL = "https://api.igdb.com/v4/covers"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
ASSETS_DIR = Path("assets/covers")


def _safe_name(text: str) -> str:
    """Create a filesystem-safe short name from text."""
    if not text:
        return "unknown"
    s = str(text)
    # keep alnum, dash, underscore
    s = re.sub(r"[^\w\-\ ]+", "", s)
    s = s.strip()
    s = s.replace(" ", "_")
    return s[:200]  # cap length


def _platform_str(platform) -> str:
    """Return a normalized lowercase platform string suitable for folder names."""
    if not platform:
        return ""
    # If platform is an enum or has .value, prefer that
    p = getattr(platform, "value", None) or str(platform)
    p = str(p)
    p = re.sub(r"[^\w\-\ ]+", "", p).strip().replace(" ", "_")
    return p.lower()


def _refresh_token_if_needed(config: dict) -> dict:
    """
    Refresh OAuth token if missing or expired.
    Modifies and saves `config` in-place and returns the igdb dict.
    """
    igdb_cfg = config.setdefault("igdb", {})
    now = int(time.time())

    # safety margin (seconds) so token is refreshed slightly before expiry
    margin = 60

    if not igdb_cfg.get("access_token") or now >= igdb_cfg.get("expires_at", 0) - margin:
        client_id = igdb_cfg.get("client_id")
        client_secret = igdb_cfg.get("client_secret")

        if not client_id or not client_secret:
            raise RuntimeError("IGDB client_id/client_secret missing in config.json")

        try:
            resp = requests.post(
                TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to refresh IGDB token: {e}")

        igdb_cfg["access_token"] = data["access_token"]
        # expires_in is seconds
        igdb_cfg["expires_at"] = now + int(data.get("expires_in", 0))

        # persist token
        try:
            save_config(config)
        except Exception:
            # non-fatal if saving fails
            pass

    return igdb_cfg


def _igdb_headers():
    """
    Get IGDB request headers, refreshing token if needed.
    """
    config = load_config()
    igdb_cfg = _refresh_token_if_needed(config)

    return {
        "Client-ID": igdb_cfg["client_id"],
        "Authorization": f"Bearer {igdb_cfg['access_token']}",
    }


def _normalize_igdb_url(url: str) -> str:
    """Normalize IGDB cover URL into an absolute https URL and prefer larger size."""
    if not url:
        return url
    u = str(url).strip()
    # protocol-relative -> https
    if u.startswith("//"):
        u = "https://" + u.lstrip("/")
    # upgrade common IGDB size tokens to a bigger cover
    u = u.replace("/t_thumb/", "/t_cover_big/").replace("/t_small/", "/t_cover_big/").replace("/t_logo_med/", "/t_cover_big/")
    return u


def fetch_cover(name: str, platform=None) -> str | None:
    """
    Fetch cover image for a game by name (optionally platform).
    Returns local path string on success, else None.

    The function will:
     - check for assets/covers/<platform>/<safe_name>.jpg
     - check for assets/covers/<safe_name>.jpg
     - try IGDB lookup/download and save into the folder
    """
    try:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # best-effort; continue
        pass

    safe_name = _safe_name(name)
    platform_folder = _platform_str(platform)

    # platform-specific local
    if platform_folder:
        platform_cover = ASSETS_DIR / platform_folder / f"{safe_name}.jpg"
        if platform_cover.exists():
            return str(platform_cover)

    # generic local
    generic_cover = ASSETS_DIR / f"{safe_name}.jpg"
    if generic_cover.exists():
        return str(generic_cover)

    # IGDB lookup
    try:
        headers = _igdb_headers()

        # Search game by name (escape quotes by doubling)
        qname = name.replace('"', '\\"')
        query = f'search "{qname}"; fields id, name, cover; limit 1;'
        resp = requests.post(IGDB_API_URL, headers=headers, data=query, timeout=10)
        resp.raise_for_status()
        games = resp.json()
        if not games:
            return None

        game = games[0]
        cover_id = game.get("cover")
        if not cover_id:
            return None

        # Fetch cover details
        cquery = f"fields url; where id = {int(cover_id)};"
        resp = requests.post(COVERS_API_URL, headers=headers, data=cquery, timeout=10)
        resp.raise_for_status()
        cover_data = resp.json()
        if not cover_data:
            return None

        cover_url = cover_data[0].get("url")
        if not cover_url:
            return None

        cover_url = _normalize_igdb_url(cover_url)

        # download image
        dl = requests.get(cover_url, timeout=15)
        dl.raise_for_status()

        # save in platform folder if provided else in root assets
        save_dir = ASSETS_DIR / platform_folder if platform_folder else ASSETS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        save_path = save_dir / f"{safe_name}.jpg"
        with open(save_path, "wb") as fh:
            fh.write(dl.content)

        return str(save_path)

    except Exception as e:
        # log a helpful message for debugging
        log_error(f"[metadata] Failed to fetch IGDB cover for '{name}': {e}")
        return None


def enrich_game_metadata(game: GameEntry) -> GameEntry:
    """
    Enrich the GameEntry with metadata (cover local path and remote url).
    Sets:
      - game.cover_path (Path or str) when a local file is available
      - game.cover_url  (str) when IGDB returned a URL
      - game.image_path (alias for backward compatibility)
    """
    try:
        # Try to fetch local cover (this will download from IGDB if needed).
        local = fetch_cover(game.name, getattr(game, "platform", None))
        if local:
            # set multiple attributes so UI functions can find the image reliably
            try:
                game.cover_path = Path(local)
            except Exception:
                game.cover_path = str(local)
            # set image_path for older code paths
            try:
                game.image_path = Path(local)
            except Exception:
                game.image_path = str(local)

            # also attempt to set cover_url (best-effort) by re-querying IGDB for URL only
            try:
                # reuse header and search for cover url
                headers = _igdb_headers()
                qname = game.name.replace('"', '\\"')
                query = f'search "{qname}"; fields id, name, cover; limit 1;'
                resp = requests.post(IGDB_API_URL, headers=headers, data=query, timeout=10)
                resp.raise_for_status()
                games = resp.json()
                if games and games[0].get("cover"):
                    cover_id = int(games[0]["cover"])
                    cquery = f"fields url; where id = {cover_id};"
                    resp = requests.post(COVERS_API_URL, headers=headers, data=cquery, timeout=10)
                    resp.raise_for_status()
                    cover_data = resp.json()
                    if cover_data and cover_data[0].get("url"):
                        game.cover_url = _normalize_igdb_url(cover_data[0]["url"])
            except Exception:
                # ignore; cover_url is optional
                pass
    except Exception as e:
        log_error(f"Metadata fetch failed for {getattr(game, 'name', '<unknown>')}: {e}")

    return game

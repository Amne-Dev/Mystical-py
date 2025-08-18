# backend/metadata.py
"""
Metadata helper module for fetching game covers, descriptions, etc.
Improved matching logic to avoid false positives (e.g. "Sugar Sugar" for "Rocket League").

Behaviour:
 - Automatically refreshes IGDB OAuth token (reads/writes config.json via common.settings).
 - Looks for local covers under assets/covers/<platform>/<safe_name>.jpg or assets/covers/<safe_name>.jpg.
 - If not found locally, queries IGDB and chooses best candidate using token-overlap + fuzzy ratio + substring boosts.
 - Downloads chosen cover into assets/covers/... and returns local path.
 - Enable verbose debug by setting config["metadata_debug"]=true or env var MYSTICAL_METADATA_DEBUG=1
"""

from pathlib import Path
from typing import Optional, Tuple, List, Any
import re
import time
import difflib
import requests
import os

from backend.models import GameEntry
from common.utils import log_info, log_error
from common.settings import load_config, save_config

IGDB_API_URL = "https://api.igdb.com/v4/games"
COVERS_API_URL = "https://api.igdb.com/v4/covers"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
ASSETS_DIR = Path("assets/covers")


# -----------------------
# Helpers
# -----------------------
def _safe_name(text: str) -> str:
    if not text:
        return "unknown"
    s = str(text)
    s = re.sub(r"[^\w\-\ ]+", "", s)
    s = s.strip()
    s = s.replace(" ", "_")
    return s[:200]


def _platform_str(platform: Any) -> str:
    if not platform:
        return ""
    p = getattr(platform, "value", None) or str(platform)
    p = str(p)
    p = re.sub(r"[^\w\-\ ]+", "", p).strip().replace(" ", "_")
    return p.lower()


def _normalize_igdb_url(url: str) -> str:
    if not url:
        return url
    u = str(url).strip()
    if u.startswith("//"):
        u = "https://" + u.lstrip("/")
    u = u.replace("/t_thumb/", "/t_cover_big/").replace("/t_small/", "/t_cover_big/").replace("/t_logo_med/", "/t_cover_big/")
    return u


def _normalize_name_for_compare(name: str) -> str:
    if not name:
        return ""
    s = str(name).lower()
    s = s.replace("®", "").replace("™", "")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokenize_for_compare(s: str) -> List[str]:
    if not s:
        return []
    return [t for t in _normalize_name_for_compare(s).split(" ") if t]


def _debug_enabled() -> bool:
    try:
        cfg = load_config()
        if cfg.get("metadata_debug"):
            return True
    except Exception:
        pass
    return bool(os.environ.get("MYSTICAL_METADATA_DEBUG"))


def _dprint(*a, **k):
    if _debug_enabled():
        print("[metadata-debug]", *a, **k)


# -----------------------
# IGDB auth + headers
# -----------------------
def _refresh_token_if_needed(config: dict) -> dict:
    igdb_cfg = config.setdefault("igdb", {})
    now = int(time.time())
    margin = 60
    if not igdb_cfg.get("access_token") or now >= igdb_cfg.get("expires_at", 0) - margin:
        client_id = igdb_cfg.get("client_id")
        client_secret = igdb_cfg.get("client_secret")
        if not client_id or not client_secret:
            raise RuntimeError("IGDB client_id/client_secret missing in config.json")

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

        igdb_cfg["access_token"] = data["access_token"]
        igdb_cfg["expires_at"] = now + int(data.get("expires_in", 0))

        try:
            save_config(config)
        except Exception:
            pass
    return igdb_cfg


def _igdb_headers() -> dict:
    config = load_config()
    igdb_cfg = _refresh_token_if_needed(config)
    return {
        "Client-ID": igdb_cfg["client_id"],
        "Authorization": f"Bearer {igdb_cfg['access_token']}",
    }


# -----------------------
# Scoring / matching
# -----------------------
def _score_candidate(query_norm: str, qtokens: List[str], candidate_name: str) -> Tuple[float, float, float]:
    cnorm = _normalize_name_for_compare(candidate_name)
    try:
        seq = difflib.SequenceMatcher(a=query_norm, b=cnorm).ratio()
    except Exception:
        seq = 0.0

    gtokens = _tokenize_for_compare(candidate_name)
    token_overlap = (len(set(qtokens).intersection(gtokens)) / max(1, len(qtokens))) if qtokens else 0.0

    substring_boost = 0.0
    if query_norm and query_norm in cnorm:
        substring_boost = 0.25

    combined = (0.55 * token_overlap) + (0.30 * seq) + substring_boost
    if qtokens and set(qtokens).issubset(set(gtokens)):
        combined += 0.10

    combined = min(combined, 1.0)
    return combined, token_overlap, seq


def _best_igdb_game_match(query_name: str, igdb_games: Optional[List[dict]], min_threshold: float = 0.60) -> Tuple[Optional[dict], float]:
    if not igdb_games:
        return None, 0.0

    qn = _normalize_name_for_compare(query_name)
    qtokens = _tokenize_for_compare(query_name)
    best = None
    best_score = 0.0
    best_token_overlap = 0.0
    best_seq = 0.0

    for g in igdb_games:
        gname = g.get("name", "") or ""
        score, tover, seq = _score_candidate(qn, qtokens, gname)
        _dprint(f"candidate: '{gname}' score={score:.3f} token_overlap={tover:.3f} seq={seq:.3f}")
        if len(qtokens) >= 2:
            if tover < 0.5 and qn not in _normalize_name_for_compare(gname) and seq < 0.9:
                _dprint(f" rejecting '{gname}' due to insufficient token overlap/substring/seq")
                continue

        if score > best_score:
            best_score = score
            best = g
            best_token_overlap = tover
            best_seq = seq

    if best_score >= min_threshold:
        _dprint(f"selected candidate '{best.get('name')}' score={best_score:.3f} token_overlap={best_token_overlap:.3f} seq={best_seq:.3f}") # type: ignore
        return best, best_score

    _dprint(f"no candidate passes threshold (best={best_score:.3f})")
    return None, best_score


# -----------------------
# Cover fetching
# -----------------------
def fetch_cover(name: str, platform: Any = None, extra: Optional[dict] = None) -> Optional[str]:
    """
    Fetch cover image for a game by name (optionally platform).
    Returns local path string on success, else None.
    """
    try:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # normalize extra so linters know it's a dict
    if not isinstance(extra, dict):
        extra = {}

    safe_name = _safe_name(name)
    platform_folder = _platform_str(platform)

    # 1) platform-specific local
    if platform_folder:
        platform_cover = ASSETS_DIR / platform_folder / f"{safe_name}.jpg"
        if platform_cover.exists():
            return str(platform_cover)

    # 2) generic local
    generic_cover = ASSETS_DIR / f"{safe_name}.jpg"
    if generic_cover.exists():
        return str(generic_cover)

    # collect fallback candidate names (from extra / manifest hints)
    fallback_names: List[str] = []
    for k in ("raw_name", "app_name", "catalog_item_id", "DisplayName", "name"):
        v = extra.get(k)
        if v:
            fallback_names.append(str(v))

    candidates_to_try = [name] + [n for n in fallback_names if n and n != name]

    try:
        headers = _igdb_headers()
    except Exception as e:
        log_error(f"[metadata] IGDB headers error for {name}: {e}")
        return None

    # try each candidate name; use large limit for candidate pool
    for query_name in candidates_to_try:
        try:
            variants = [query_name, query_name.replace('"', '\\"'), re.sub(r'[^\w\s]', ' ', query_name).strip()]
            seen = set()
            unique_variants = []
            for v in variants:
                if v not in seen:
                    seen.add(v)
                    unique_variants.append(v)

            for variant in unique_variants:
                qname = variant.replace('"', '\\"')
                query = f'search "{qname}"; fields id, name, cover; limit 50;'
                resp = requests.post(IGDB_API_URL, headers=headers, data=query, timeout=12)
                resp.raise_for_status()
                games = resp.json()
                if not games:
                    continue

                best_game, score = _best_igdb_game_match(variant, games, min_threshold=0.60)
                if not best_game:
                    continue

                cover_id = best_game.get("cover")
                if not cover_id:
                    continue

                cquery = f"fields url; where id = {int(cover_id)};"
                resp2 = requests.post(COVERS_API_URL, headers=headers, data=cquery, timeout=12)
                resp2.raise_for_status()
                cover_data = resp2.json()
                if not cover_data or not cover_data[0].get("url"):
                    continue

                cover_url = _normalize_igdb_url(cover_data[0]["url"])

                dl = requests.get(cover_url, timeout=15)
                dl.raise_for_status()

                save_dir = ASSETS_DIR / (platform_folder if platform_folder else "")
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / f"{safe_name}.jpg"
                with open(save_path, "wb") as fh:
                    fh.write(dl.content)

                log_info(f"[metadata] downloaded cover for '{name}' from {cover_url} -> {save_path}")
                _dprint(f"[metadata] chosen game: {best_game.get('name')} (cover id {cover_id})")
                return str(save_path)

        except Exception as e:
            log_error(f"[metadata] Failed IGDB attempt for '{query_name}': {e}")
            continue

    return None


# -----------------------
# Enrichment entrypoint
# -----------------------
def enrich_game_metadata(game: GameEntry) -> GameEntry:
    try:
        extra = getattr(game, "extra", None)
        if not isinstance(extra, dict):
            extra = {}

        cover = fetch_cover(game.name, getattr(game, "platform", None), extra=extra)
        if cover:
            try:
                game.cover_path = Path(cover)
            except Exception:
                game.cover_path = str(cover)
            try:
                game.image_path = Path(cover)
            except Exception:
                game.image_path = str(cover)
    except Exception as e:
        log_error(f"Metadata fetch failed for {getattr(game, 'name', '<unknown>')}: {e}")

    return game

import time
import requests
from common.settings import load_config, save_config

TOKEN_URL = "https://id.twitch.tv/oauth2/token"

def get_igdb_token() -> str:
    config = load_config()
    igdb_cfg = config.get("igdb", {})

    client_id = igdb_cfg.get("client_id")
    client_secret = igdb_cfg.get("client_secret")
    access_token = igdb_cfg.get("access_token")
    expires_at = igdb_cfg.get("expires_at", 0)

    # If token is valid for another 5 minutes → reuse it
    if access_token and time.time() < expires_at - 300:
        return access_token

    # Else refresh
    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    })
    resp.raise_for_status()
    data = resp.json()

    new_token = data["access_token"]
    expires_in = data["expires_in"]

    # Save new token
    igdb_cfg["access_token"] = new_token
    igdb_cfg["expires_at"] = int(time.time()) + expires_in
    config["igdb"] = igdb_cfg
    save_config(config)

    return new_token

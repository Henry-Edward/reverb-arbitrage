"""
Config Loader
Reads config.json (written by the web UI) with sensible defaults.
Also reads secrets from environment variables for GitHub Actions.
"""

import json
import os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULTS = {
    "ntfy_topic": "",
    "default_min_profit": 15.0,
    "skip_red_flags": True,
    "use_price_guide": True,
    "watches": [
        {
            "query": "Shure SM57",
            "enabled": True,
            "min_profit": 15,
            "max_buy_price": 80,
            "scan_limit": 30,
            "condition_slugs": [],
            "notes": "Classic dynamic mic - high liquidity",
        },
        {
            "query": "Focusrite Scarlett Solo",
            "enabled": True,
            "min_profit": 20,
            "max_buy_price": 60,
            "scan_limit": 30,
            "condition_slugs": [],
            "notes": "Best-selling audio interface",
        },
        {
            "query": "Boss DS-1",
            "enabled": True,
            "min_profit": 12,
            "max_buy_price": 35,
            "scan_limit": 30,
            "condition_slugs": [],
            "notes": "Ubiquitous distortion pedal",
        },
        {
            "query": "Electro-Harmonix Big Muff",
            "enabled": False,
            "min_profit": 20,
            "max_buy_price": 60,
            "scan_limit": 30,
            "condition_slugs": [],
            "notes": "Disable/enable per your capital",
        },
    ],
}


def load_config() -> dict:
    config = DEFAULTS.copy()

    # Load from file if it exists
    if CONFIG_FILE.exists():
        try:
            file_config = json.loads(CONFIG_FILE.read_text())
            config.update(file_config)
        except Exception as e:
            print(f"[WARN] Could not read config.json: {e}. Using defaults.")

    # Environment variable overrides (for GitHub Actions secrets)
    if os.getenv("NTFY_TOPIC"):
        config["ntfy_topic"] = os.getenv("NTFY_TOPIC")

    return config


def save_config(config: dict):
    """Write config back to file (called by web UI)."""
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

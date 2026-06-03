import os
import json
from pathlib import Path
from typing import Dict, Optional

CONFIG_DIR = Path.home() / ".pr_today"
CONFIG_FILE = CONFIG_DIR / "config.json"

def init_config_dir():
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> Dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_config(config: Dict[str, str]):
    init_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def get_token(service: str) -> Optional[str]:
    # Try env var first
    env_token = os.environ.get(f"{service.upper()}_TOKEN")
    if env_token:
        return env_token
    
    config = load_config()
    return config.get(f"{service}_token")

def set_token(service: str, token: str):
    config = load_config()
    config[f"{service}_token"] = token
    save_config(config)

def get_github_token() -> Optional[str]:
    # GITHUB_PAT is standard in our docs
    env_token = os.environ.get("GITHUB_PAT")
    if env_token:
        return env_token
    config = load_config()
    return config.get("github_token")

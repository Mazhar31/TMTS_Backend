import os
import json

SETTINGS_FILE = "app/static/settings.json"

# Default fallback settings
DEFAULT_SETTINGS = {
    "business_name": "",
    "business_address": "",
    "hashtags": "",
    "caption_templates": [
        ""
    ],
    "max_photos": 50,
    "post_interval_minutes": 3,
    "page_title": "TMTSelfie Booth",
    "logo_filename": "",
    "background_filename": ""
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            return {**DEFAULT_SETTINGS, **settings}  # Merge with defaults
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

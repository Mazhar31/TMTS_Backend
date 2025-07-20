import os
import time
import requests
from app.utils.fb_data import load_fb_data, save_fb_data
from app.models.settings import load_settings, save_settings


def refresh_fb_page_token_if_needed(short_lived_user_token: str) -> str:
    fb_data = load_fb_data()
    page_id = fb_data.get("page_id")
    stored_token = fb_data.get("user_token")
    token_expiry = fb_data.get("token_expiry", 0)

    # Skip reuse if token was not acquired via long-lived user token → page access
    is_initial_short_token = token_expiry == 0 or token_expiry < time.time()

    if stored_token and not is_initial_short_token:
        print("🔁 Reusing cached page token.")
        return stored_token

    print("🔄 Refreshing page access token...")

    # Step 1: Exchange short-lived user token for long-lived user token
    exchange_url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": fb_data["app_id"],
        "client_secret": fb_data["app_secret"],
        "fb_exchange_token": short_lived_user_token
    }

    res = requests.get(exchange_url, params=params)
    res.raise_for_status()
    exchange_data = res.json()

    long_lived_user_token = exchange_data["access_token"]
    expires_in = exchange_data.get("expires_in", 60 * 24 * 60 * 60)  # fallback ~60 days
    token_expiry = int(time.time()) + expires_in

    # Step 2: Use long-lived token to get Page access token
    pages_url = "https://graph.facebook.com/v18.0/me/accounts"
    res = requests.get(pages_url, params={"access_token": long_lived_user_token})
    res.raise_for_status()
    pages = res.json().get("data", [])

    page_token = None
    for page in pages:
        if page["id"] == page_id:
            page_token = page["access_token"]
            break

    if not page_token:
        raise Exception("❌ Page token not found for your Page ID.")

    # Step 3: Save the non-expiring page token + optional expiry timestamp
    fb_data["user_token"] = page_token
    fb_data["token_expiry"] = token_expiry
    save_fb_data(fb_data)

    print("✅ New long-lived page token saved.")
    return page_token


def post_photo_to_facebook(image_path: str, frontend_user_token: str = None):
    settings = load_settings()
    fb_data = load_fb_data()

    if fb_data.get("token_expiry", 0) == 0:
        token = refresh_fb_page_token_if_needed(fb_data.get("user_token"))
    else:
        token = fb_data.get("user_token")

    page_id = fb_data.get("page_id")
    print("🔐 TOKEN USED:", token[:50], "...")
    print("📄 PAGE ID:", page_id)

    if not token or not page_id:
        print("❌ Missing Facebook credentials.")
        return

    # Rotate captions
    captions = settings.get("caption_templates", [])
    index = settings.get("caption_index", 0)
    caption_template = captions[index % len(captions)] if captions else ""

    # Format hashtags and final caption
    raw_hashtags = settings.get("hashtags", "")
    hashtag_list = [f"#{tag.strip().replace(' ', '')}" for tag in raw_hashtags.split(",") if tag.strip()]
    formatted_hashtags = " ".join(hashtag_list)
    caption = f"{caption_template}\n\n{settings.get('business_name')}, {settings.get('business_address')}\n{formatted_hashtags}"

    # Update rotation index
    settings["caption_index"] = index + 1
    save_settings(settings)

    try:
        with open(image_path, 'rb') as image_file:
            files = {'source': image_file}
            data = {
                'caption': caption,
                'access_token': token
            }

            endpoint = f"https://graph.facebook.com/v18.0/{page_id}/photos"
            response = requests.post(endpoint, files=files, data=data)
    except FileNotFoundError:
        print(f"❌ Image not found: {image_path}")
        return

    if response.status_code == 200:
        print("✅ Posted to Facebook successfully.")
    else:
        print(f"❌ Failed to post: {response.status_code} - {response.text}")

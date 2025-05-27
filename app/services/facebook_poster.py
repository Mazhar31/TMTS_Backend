import os
import requests
from app.utils.fb_data import load_fb_data, save_fb_data
from app.models.settings import load_settings, save_settings

def refresh_facebook_tokens():
    fb_data = load_fb_data()

    app_id = fb_data["app_id"]
    app_secret = fb_data["app_secret"]
    user_token = fb_data["user_token"]
    page_id = fb_data["page_id"]

    # Step 1: Get a new long-lived user token
    token_url = "https://graph.facebook.com/v12.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": user_token
    }

    user_token_response = requests.get(token_url, params=params)
    user_token_response.raise_for_status()
    long_lived_user_token = user_token_response.json()["access_token"]

    # Step 2: Get the page access token
    pages_url = "https://graph.facebook.com/v12.0/me/accounts"
    pages_response = requests.get(pages_url, params={"access_token": long_lived_user_token})
    pages_response.raise_for_status()
    pages_data = pages_response.json()["data"]

    page_token = None
    for page in pages_data:
        if page["id"] == page_id:
            page_token = page["access_token"]
            break

    if not page_token:
        raise Exception("Page access token not found")

    # Save updated tokens
    fb_data["user_token"] = long_lived_user_token
    fb_data["page_token"] = page_token
    save_fb_data(fb_data)

    return page_token


def post_photo_to_facebook(image_path: str):
    settings = load_settings()
    token = refresh_facebook_tokens()

    fb_data = load_fb_data()
    page_id = fb_data["page_id"]

    if not token or not page_id:
        print("❌ Missing Facebook credentials.")
        return

    # Rotate captions
    captions = settings.get("caption_templates", [])
    index = settings.get("caption_index", 0)
    caption_template = captions[index % len(captions)]

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
            files = {
                'source': image_file
            }
            data = {
                'caption': caption,
                'access_token': token
            }

            endpoint = f"https://graph.facebook.com/{page_id}/photos"
            response = requests.post(endpoint, files=files, data=data)
    except FileNotFoundError:
        print(f"❌ Image not found: {image_path}")
        return

    if response.status_code == 200:
        print("✅ Posted to Facebook successfully.")
    else:
        print(f"❌ Failed to post: {response.status_code} - {response.text}")

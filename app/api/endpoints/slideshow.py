import os
from fastapi import APIRouter
from app.models.settings import load_settings

router = APIRouter()

CAPTURED_DIR = "app/static/captured_images"
BASE_IMAGE_URL = "/static/captured_images/"

@router.get("/")
def get_slideshow_photos():
    settings = load_settings()
    max_photos = settings.get("max_photos", 50)

    if not os.path.exists(CAPTURED_DIR):
        return {
            "photos": [],
            "logo": settings.get("logo_filename", ""),
            "title": settings.get("page_title", "")
        }

    # Get all images, sort by newest first
    files = [
        f for f in os.listdir(CAPTURED_DIR)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
    ]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(CAPTURED_DIR, x)), reverse=True)

    photos = [BASE_IMAGE_URL + filename for filename in files[:max_photos]]

    return {
        "photos": photos,
        "logo": settings.get("logo_filename", ""),
        "title": settings.get("page_title", ""),
        "background": settings.get("background_filename", "")
    }

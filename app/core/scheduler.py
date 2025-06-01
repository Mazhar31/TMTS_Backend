import os
import json
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.facebook_poster import post_photo_to_facebook
from app.models.settings import load_settings

POST_QUEUE_FILE = "app/static/queue.json"
CAPTURED_DIR = "app/static/captured_images"

scheduler = BackgroundScheduler()

def process_queue():
    if not os.path.exists(POST_QUEUE_FILE):
        return

    with open(POST_QUEUE_FILE, "r") as f:
        queue = json.load(f)

    if not queue:
        return

    settings = load_settings()
    interval_minutes = settings.get("post_interval_minutes", 3)

    next_item = queue.pop(0)
    filename = next_item["filename"]

    image_path = os.path.join(CAPTURED_DIR, filename)

    try:
        post_photo_to_facebook(image_path)
    except Exception as e:
        print(f"Failed to post {filename}: {e}")
        queue.insert(0, next_item)  # Requeue
        return

    # Save updated queue
    with open(POST_QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=4)

    # Enforce max photo count
    max_photos = settings.get("max_photos", 50)
    photos = sorted(
        os.listdir(CAPTURED_DIR),
        key=lambda x: os.path.getctime(os.path.join(CAPTURED_DIR, x))
    )
    while len(photos) > max_photos:
        to_delete = photos.pop(0)
        os.remove(os.path.join(CAPTURED_DIR, to_delete))

def start_scheduler():
    settings = load_settings()
    interval_minutes = settings.get("post_interval_minutes", 3)
    scheduler.add_job(process_queue, "interval", minutes=interval_minutes)
    scheduler.start()

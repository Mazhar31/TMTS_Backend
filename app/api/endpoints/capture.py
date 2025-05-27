import os
import uuid
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

CAPTURED_DIR = "app/static/captured_images"
POST_QUEUE_FILE = "app/static/queue.json"

router = APIRouter()

# Ensure necessary directories exist
os.makedirs(CAPTURED_DIR, exist_ok=True)

def save_to_post_queue(filename: str):
    import json

    if not os.path.exists(POST_QUEUE_FILE):
        queue = []
    else:
        with open(POST_QUEUE_FILE, "r") as f:
            queue = json.load(f)

    queue.append({
        "filename": filename,
        "timestamp": datetime.utcnow().isoformat()
    })

    with open(POST_QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=4)

@router.post("/upload")
async def upload_photo(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Unique filename generation
    ext = file.filename.split(".")[-1]
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(CAPTURED_DIR, unique_name)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        save_to_post_queue(unique_name)

        return JSONResponse(content={"message": "Photo uploaded", "filename": unique_name}, status_code=201)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving photo: {str(e)}")

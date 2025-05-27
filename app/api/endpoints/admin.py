import os
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends
)
from fastapi.responses import JSONResponse
from typing import List
from sqlalchemy.orm import Session
import requests  # ✅ For Facebook API call
from pydantic import BaseModel  # ✅ For request validation

from app.models.settings import load_settings, save_settings
from app.database import SessionLocal
from app.core.security import AdminUser, pwd_context
from app.api.endpoints.auth import get_current_user
from app.utils.fb_data import save_fb_data


SETTINGS_DIR = "app/static"
UPLOADS_DIR = os.path.join(SETTINGS_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

router = APIRouter()

# --- Dependency to get DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Signup route ---
@router.post("/signup")
def signup(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(AdminUser).filter(AdminUser.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Admin already exists")

    hashed_pw = pwd_context.hash(password)
    user = AdminUser(email=email, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Signup successful"}

# --- Get Settings (public or protected) ---
@router.get("/settings")
def get_settings():
    return load_settings()

# --- Update Settings (🔒 Requires login) ---
@router.post("/settings")
def update_settings(
    business_name: str = Form(...),
    business_address: str = Form(...),
    hashtags: str = Form(...),
    caption_templates: List[str] = Form(...),
    max_photos: int = Form(...),
    post_interval_minutes: int = Form(...),
    page_title: str = Form(...),
    user: str = Depends(get_current_user)
):
    if not (15 <= max_photos <= 99):
        raise HTTPException(status_code=400, detail="max_photos must be between 15 and 99")

    settings = {
        "business_name": business_name,
        "business_address": business_address,
        "hashtags": hashtags,
        "caption_templates": caption_templates,
        "max_photos": max_photos,
        "post_interval_minutes": post_interval_minutes,
        "page_title": page_title
    }

    current = load_settings()
    current.update(settings)
    save_settings(current)

    return JSONResponse(content={"message": "Settings updated"}, status_code=200)

# --- Upload Logo (🔒) ---
@router.post("/upload/logo")
async def upload_logo(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user)
):
    filename = "logo_" + file.filename
    path = os.path.join(UPLOADS_DIR, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    current = load_settings()
    current["logo_filename"] = f"/static/uploads/{filename}"
    save_settings(current)

    return {"message": "Logo uploaded", "url": current["logo_filename"]}

# --- Upload Background (🔒) ---
@router.post("/upload/background")
async def upload_background(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user)
):
    filename = "background_" + file.filename
    path = os.path.join(UPLOADS_DIR, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    current = load_settings()
    current["background_filename"] = f"/static/uploads/{filename}"
    save_settings(current)

    return {"message": "Background uploaded", "url": current["background_filename"]}

# --- Facebook Page Connection (🔒) ---

class FacebookPageCredentials(BaseModel):
    app_id: str
    app_secret: str
    user_token: str
    page_id: str

@router.post("/page_connection")
def connect_facebook_page(
    creds: FacebookPageCredentials,
    user: str = Depends(get_current_user)
):
    # Try to validate page ID using the provided user token
    graph_url = f"https://graph.facebook.com/v18.0/{creds.page_id}?fields=name&access_token={creds.user_token}"

    try:
        response = requests.get(graph_url)
        response.raise_for_status()
        result = response.json()

        page_name = result.get("name")
        if not page_name:
            raise HTTPException(status_code=400, detail="Invalid page ID or access token")

        # Save to fb_data.json
        fb_data = {
            "app_id": creds.app_id,
            "app_secret": creds.app_secret,
            "user_token": creds.user_token,
            "page_id": creds.page_id,
            "page_token": ""  # optional: leave empty; will be refreshed on first post
        }
        save_fb_data(fb_data)

        return {"message": "Facebook page connected successfully", "page_name": page_name}

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Facebook API error: {str(e)}")
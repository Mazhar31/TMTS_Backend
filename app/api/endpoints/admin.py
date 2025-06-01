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
from app.utils.fb_data import load_fb_data


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

# --- Create Super User (One-time setup) ---
@router.post("/create-superuser")
def create_superuser(
    email: str = Form(...),
    password: str = Form(...),
    secret_key: str = Form(...),  # Add a secret key for extra security
    db: Session = Depends(get_db)
):
    # Check if secret key matches (you can set this in environment variables)
    SUPER_USER_SECRET = os.getenv("SUPER_USER_SECRET", "12345")
    if secret_key != SUPER_USER_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    # Check if super user already exists
    existing_super_user = db.query(AdminUser).filter(AdminUser.is_super_user == True).first()
    if existing_super_user:
        raise HTTPException(status_code=400, detail="Super user already exists")

    hashed_pw = pwd_context.hash(password)
    super_user = AdminUser(
        email=email, 
        hashed_password=hashed_pw,
        is_super_user=True,
        is_approved=True,
        is_active=True
    )
    db.add(super_user)
    db.commit()
    db.refresh(super_user)
    return {"message": "Super user created successfully"}

# --- Signup route (now creates pending accounts) ---
@router.post("/signup")
def signup(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(AdminUser).filter(AdminUser.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed_pw = pwd_context.hash(password)
    user = AdminUser(
        email=email, 
        hashed_password=hashed_pw,
        is_super_user=False,
        is_approved=False,  # Pending approval
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Signup request submitted. Please wait for admin approval."}

# --- Get all users (Super user only) ---
@router.get("/users")
def get_all_users(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get current user details
    user = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not user or not user.is_super_user:
        raise HTTPException(status_code=403, detail="Only super user can access this")
    
    users = db.query(AdminUser).all()
    user_list = []
    for u in users:
        user_list.append({
            "id": u.id,
            "email": u.email,
            "is_super_user": u.is_super_user,
            "is_approved": u.is_approved,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if hasattr(u, 'created_at') and u.created_at else None
        })
    
    return {"users": user_list}

# --- Approve/Reject user (Super user only) ---
@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: int,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is super user
    current_user_obj = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not current_user_obj or not current_user_obj.is_super_user:
        raise HTTPException(status_code=403, detail="Only super user can approve users")
    
    user_to_approve = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user_to_approve:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_to_approve.is_approved = True
    db.commit()
    return {"message": f"User {user_to_approve.email} approved successfully"}

@router.post("/users/{user_id}/reject")
def reject_user(
    user_id: int,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is super user
    current_user_obj = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not current_user_obj or not current_user_obj.is_super_user:
        raise HTTPException(status_code=403, detail="Only super user can reject users")
    
    user_to_reject = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user_to_reject:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_to_reject.is_super_user:
        raise HTTPException(status_code=403, detail="Cannot reject super user")
    
    db.delete(user_to_reject)
    db.commit()
    return {"message": f"User {user_to_reject.email} rejected and deleted"}

# --- Toggle user active status (Super user only) ---
@router.post("/users/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is super user
    current_user_obj = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not current_user_obj or not current_user_obj.is_super_user:
        raise HTTPException(status_code=403, detail="Only super user can manage user status")
    
    user_to_toggle = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user_to_toggle:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_to_toggle.is_super_user:
        raise HTTPException(status_code=403, detail="Cannot deactivate super user")
    
    user_to_toggle.is_active = not user_to_toggle.is_active
    db.commit()
    
    status = "activated" if user_to_toggle.is_active else "deactivated"
    return {"message": f"User {user_to_toggle.email} {status} successfully"}

# --- Delete user (Super user only) ---
@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is super user
    current_user_obj = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not current_user_obj or not current_user_obj.is_super_user:
        raise HTTPException(status_code=403, detail="Only super user can delete users")
    
    user_to_delete = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_to_delete.is_super_user:
        raise HTTPException(status_code=403, detail="Cannot delete super user")
    
    email = user_to_delete.email
    db.delete(user_to_delete)
    db.commit()
    return {"message": f"User {email} deleted successfully"}

# --- Change user password (Super user only) ---
@router.post("/users/{user_id}/change-password")
def change_user_password(
    user_id: int,
    new_password: str = Form(...),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if current user is super user
    current_user_obj = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not current_user_obj or not current_user_obj.is_super_user:
        raise HTTPException(status_code=403, detail="Only super user can change passwords")
    
    user_to_update = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    
    # Hash the new password
    hashed_pw = pwd_context.hash(new_password)
    user_to_update.hashed_password = hashed_pw
    db.commit()
    
    return {"message": f"Password changed successfully for {user_to_update.email}"}

# --- Change own password ---
@router.post("/change-own-password")
def change_own_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not pwd_context.verify(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    
    # Hash the new password
    hashed_pw = pwd_context.hash(new_password)
    user.hashed_password = hashed_pw
    db.commit()
    
    return {"message": "Your password has been changed successfully"}

# --- Check if current user is super user ---
@router.get("/user-info")
def get_user_info(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(AdminUser).filter(AdminUser.email == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": user.email,
        "is_super_user": user.is_super_user,
        "is_approved": user.is_approved,
        "is_active": user.is_active
    }

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
    
@router.get("/facebook-page-url")
def get_facebook_page_url():
    """
    Returns the Facebook page URL that can be opened in a browser
    """
    try:
        fb_data = load_fb_data()
        page_id = fb_data.get("page_id")
        
        if not page_id:
            raise HTTPException(status_code=404, detail="Facebook page not connected")
        
        # Construct the Facebook page URL
        page_url = f"https://www.facebook.com/{page_id}"
        
        return {
            "page_url": page_url,
            "page_id": page_id,
            "message": "Facebook page URL retrieved successfully"
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Facebook configuration not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving Facebook page URL: {str(e)}")
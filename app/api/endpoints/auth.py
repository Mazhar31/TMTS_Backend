from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.security import AdminUser, pwd_context
from app.database import SessionLocal

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Secret & settings
SECRET_KEY = "your-secret-key"  # Replace with an environment variable in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# Dependency: Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# JWT creation
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Login route (Updated with approval and active status checks)
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.email == form_data.username).first()

    # Check if user exists and password is correct
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is approved (new check)
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please contact administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active (new check)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

# Auth guard for protected routes (Updated with additional checks)
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Additional check: verify user still exists and is active/approved
        user = db.query(AdminUser).filter(AdminUser.email == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.is_approved:
            raise HTTPException(status_code=403, detail="Account no longer approved")
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account has been deactivated")
        
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
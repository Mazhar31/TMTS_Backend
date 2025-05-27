from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import auth, capture, admin, slideshow
from app.core.scheduler import start_scheduler

# 👇 Add these imports
from app.core.security import Base  # SQLAlchemy Base
from app.database import engine

app = FastAPI(title="TMTSelfie Backend")

# CORS setup (update origin if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (e.g., images, uploaded logo/background)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

# API Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(capture.router, prefix="/api/capture", tags=["capture"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(slideshow.router, prefix="/api/slideshow", tags=["slideshow"])

# Start background scheduler (for posting queue)
@app.on_event("startup")
async def startup_event():
    start_scheduler()

from fastapi import (
    FastAPI, Request, Form, UploadFile, File,
    HTTPException, Query, Depends
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from db import (
    init_db, add_complaint, get_all_complaints,
    get_complaints_by_status, get_completed_complaints,
    update_complaint_status, move_to_completed,
    get_status_counts,
    get_processing_history
)
import os
import shutil
from datetime import datetime
import secrets
from typing import Optional
from compress import compress_image_to_webp
app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

os.makedirs("uploads", exist_ok=True)
# Admin credentials
security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """Verify admin credentials"""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with complaint categories"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/complain/{category}", response_class=HTMLResponse)
async def complain_form(request: Request, category: str):
    """Complaint submission form"""
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "category": category}
    )


@app.post("/submit")
async def submit_complaint(
    request: Request,
    category: str = Form(...),
    desc: str = Form(None),
    full_name: str = Form(...),
    phone: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    image: UploadFile = File(...)
):
    """Handle complaint submission"""
    # Validate phone number
    if not phone.isdigit() or len(phone) < 8:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    try:
        # Compress and save the image
        image_path = compress_image_to_webp(image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
    
    # Add complaint to database
    add_complaint(
        category=category,
        description=desc or "",
        full_name=full_name,
        phone=phone,
        lat=lat,
        lng=lng,
        image=image_path
    )
    
    return RedirectResponse("/map", status_code=302)

@app.get("/map", response_class=HTMLResponse)
async def show_map(
    request: Request,
    period: Optional[str] = Query(None)
):
    """Show interactive map with complaints"""
    complaints = get_all_complaints(period)
    
    # Convert complaints to JSON-serializable format
    complaints_data = []
    for complaint in complaints:
        complaints_data.append({
            "id": complaint["id"],
            "category": complaint["category"],
            "description": complaint["description"],
            "full_name": complaint["full_name"],
            "phone": complaint["phone"],
            "lat": complaint["lat"],
            "lng": complaint["lng"],
            "image": complaint["image"],
            "created_at": complaint["created_at"],
            "status": complaint["status"]
        })
    
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "complaints": complaints_data,
            "period": period
        }
    )

# Admin routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    period: Optional[str] = Query(None),
    authorized: bool = Depends(verify_admin)
):
    """Admin dashboard showing all complaints"""
    complaints = get_all_complaints(period)
    stats = get_status_counts(period)
    
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "complaints": complaints,
            "stats": stats,
            "period": period
        }
    )

@app.get("/admin/complaints/pending", response_class=HTMLResponse)
async def pending_complaints(
    request: Request,
    period: Optional[str] = Query(None),
    authorized: bool = Depends(verify_admin)
):
    """View pending complaints"""
    complaints = get_complaints_by_status("pending", period)
    # Fix image paths
    fixed_complaints = []
    for complaint in complaints:
        fixed_complaint = dict(complaint)
        if fixed_complaint["image"] and not fixed_complaint["image"].startswith("/uploads/"):
            fixed_complaint["image"] = "/uploads/" + fixed_complaint["image"].split("uploads/")[-1]
        fixed_complaints.append(fixed_complaint)
    
    stats = get_status_counts(period)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "complaints": fixed_complaints,
            "period": period,
            "status_filter": "pending",
            "stats": stats
        }
    )


@app.get("/admin/complaints/processing", response_class=HTMLResponse)
async def processing_complaints(
    request: Request,
    period: Optional[str] = Query(None),
    authorized: bool = Depends(verify_admin)
):
    """View processing complaints"""
    complaints = get_complaints_by_status("processing", period)
    # Fix image paths
    fixed_complaints = []
    for complaint in complaints:
        fixed_complaint = dict(complaint)
        if fixed_complaint["image"] and not fixed_complaint["image"].startswith("/uploads/"):
            fixed_complaint["image"] = "/uploads/" + fixed_complaint["image"].split("uploads/")[-1]
        fixed_complaints.append(fixed_complaint)
    
    stats = get_status_counts(period)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "complaints": fixed_complaints,
            "period": period,
            "status_filter": "processing",
            "stats": stats
        }
    )

@app.get("/admin/complaints/completed", response_class=HTMLResponse)
async def completed_complaints(
    request: Request,
    period: Optional[str] = Query(None),
    authorized: bool = Depends(verify_admin)
):
    """View completed complaints"""
    complaints = get_completed_complaints(period)
    # Fix image paths
    fixed_complaints = []
    for complaint in complaints:
        fixed_complaint = dict(complaint)
        if fixed_complaint["image"] and not fixed_complaint["image"].startswith("/uploads/"):
            fixed_complaint["image"] = "/uploads/" + fixed_complaint["image"].split("uploads/")[-1]
        fixed_complaints.append(fixed_complaint)
    
    stats = get_status_counts(period)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "complaints": fixed_complaints,
            "period": period,
            "status_filter": "completed",
            "stats": stats
        }
    )


@app.post("/update-status")
async def update_status(
    request: Request,
    complaint_id: int = Form(...),
    status: str = Form(...),
    authorized: bool = Depends(verify_admin)
):
    """Update complaint status"""
    update_complaint_status(complaint_id, status)
    return RedirectResponse(
        request.headers.get('referer', '/admin'),
        status_code=302
    )

@app.post("/complete")
async def complete_complaint(
    request: Request,
    complaint_id: int = Form(...),
    admin_notes: str = Form(None),
    authorized: bool = Depends(verify_admin)
):
    """Mark complaint as completed"""
    move_to_completed(complaint_id, admin_notes or "")
    return RedirectResponse(
        request.headers.get('referer', '/admin'),
        status_code=302
    )

@app.get("/admin/history/{complaint_id}", response_class=HTMLResponse)
async def view_complaint_history(
    request: Request,
    complaint_id: int,
    authorized: bool = Depends(verify_admin)
):
    """View processing history for a complaint"""
    history = get_processing_history(complaint_id)
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "history": history,
            "complaint_id": complaint_id
        }
    )

# Initialize database on startup
init_db()
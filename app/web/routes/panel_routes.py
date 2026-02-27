from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import json
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD
from app.web.services.admin_service import AdminService

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
security = HTTPBasic()

# Проста авторизація
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, period: str = "week", username: str = Depends(get_current_username)):
    stats = await AdminService.get_dashboard_stats()
    chart_data = await AdminService.get_chart_data(period)
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "stats": stats,
        "chart_data": json.dumps(chart_data),
        "username": username,
        "page": "dashboard",
        "period": period
    })

@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, username: str = Depends(get_current_username)):
    users = await AdminService.get_all_users()
    return templates.TemplateResponse("users.html", {
        "request": request, 
        "users": users,
        "page": "users"
    })

@router.get("/vinyls", response_class=HTMLResponse)
async def vinyls_list(request: Request, username: str = Depends(get_current_username)):
    vinyls_data = await AdminService.get_all_vinyls()
    return templates.TemplateResponse("vinyls.html", {
        "request": request,
        "vinyls_data": vinyls_data,
        "page": "vinyls"
    })

@router.get("/vinyls/{vinyl_id}", response_class=HTMLResponse)
async def vinyl_profile(request: Request, vinyl_id: int, username: str = Depends(get_current_username)):
    details = await AdminService.get_vinyl_details(vinyl_id)
    if not details:
        raise HTTPException(status_code=404, detail="Vinyl not found")
    
    return templates.TemplateResponse("vinyl_profile.html", {
        "request": request,
        "vinyl": details["vinyl"],
        "owner": details["owner"],
        "username": username,
        "page": "vinyls"
    })

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_profile(request: Request, user_id: int, username: str = Depends(get_current_username)):
    details = await AdminService.get_user_details(user_id)
    if not details:
        raise HTTPException(status_code=404, detail="User not found")
    
    logs = AdminService.get_user_logs(details["user"].telegram_id)
    
    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "user": details["user"],
        "vinyl_count": details["vinyl_count"],
        "vinyls": details["vinyls"],
        "logs": logs,
        "username": username,
        "page": "users"
    })

@router.post("/users/toggle/{user_id}", name="toggle_user_status")
async def toggle_user(user_id: int, username: str = Depends(get_current_username)):
    await AdminService.toggle_user_active(user_id)
    return RedirectResponse(url="/web/users", status_code=303)

@router.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request, username: str = Depends(get_current_username)):
    logs = AdminService.get_logs()
    return templates.TemplateResponse("logs.html", {
        "request": request, 
        "logs": logs,
        "page": "logs"
    })

@router.post("/logs/clear")
async def clear_logs(username: str = Depends(get_current_username)):
    AdminService.clear_logs()
    return RedirectResponse(url="/web/logs", status_code=303)
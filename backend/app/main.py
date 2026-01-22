from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import os
import traceback
import re
from dotenv import load_dotenv

from app.services.supabase_db import SupabaseDBService
from app.processor import InvoiceProcessor
from app.metrics import setup_metrics
from app.auth import verify_user_token

load_dotenv()

app = FastAPI(title="InvoiceToSheet AI API")


def normalize_google_sheet_id(value: Optional[str]) -> Optional[str]:
    """
    Accepts either a Google Sheets URL or a raw spreadsheet ID and returns the ID.
    Example URL: https://docs.google.com/spreadsheets/d/<ID>/edit?...
    """
    if not value:
        return value
    v = value.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", v)
    return m.group(1) if m else v

# Add exception handler to log errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] Error on {request.url.path}:")
    print(f"   Exception: {type(exc).__name__}: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# CORS configuration
# Dev-friendly: allow localhost on any port + common LAN ranges.
# In production, restrict this to your real frontend domain(s).
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        frontend_url,
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Prometheus metrics
metrics_app = setup_metrics()
app.mount("/metrics", metrics_app)

@app.get("/")
async def root():
    return {"message": "InvoiceToSheet AI API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/process-invoice")
async def process_invoice(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """
    Process an uploaded invoice file:
    1. Verify user authentication
    2. Check monthly usage limit
    3. Extract invoice data using OpenAI
    4. Write to Google Sheets
    5. Log usage
    """
    try:
        # Verify user token
        user_id = verify_user_token(authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        # Initialize Supabase DB service
        db_service = SupabaseDBService()
        
        # Get user profile from Supabase
        profile = db_service.get_user_profile(user_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        # Check monthly usage limit
        current_usage, monthly_limit = db_service.check_monthly_usage_limit(user_id)
        
        if current_usage >= monthly_limit:
            raise HTTPException(status_code=429, detail=f"Monthly limit of {monthly_limit} reached")
        
        # Check if user has Google refresh token and sheet ID
        if not profile.get("google_refresh_token"):
            raise HTTPException(status_code=400, detail="Google refresh token not found. Please authenticate with Google.")
        
        sheet_id = normalize_google_sheet_id(profile.get("target_sheet_id"))
        if not sheet_id:
            raise HTTPException(status_code=400, detail="Target Sheet ID not configured")
        
        # Get user's entreprise_id
        entreprise_id = db_service.get_user_entreprise_id(user_id)
        
        # Create usage log entry
        log_id = db_service.create_usage_log(
            user_id=user_id,
            entreprise_id=entreprise_id,
            file_name=file.filename or "invoice",
            file_size=file.size if hasattr(file, 'size') else None
        )
        
        # Process invoice
        processor = InvoiceProcessor(
            user_id=user_id,
            log_id=log_id
        )
        
        result = await processor.process_invoice(
            file=file,
            refresh_token=profile["google_refresh_token"],
            sheet_id=sheet_id
        )
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        # Error handling is done in processor, but ensure log is updated and logged
        print(f"[ERROR] process_invoice failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        msg = str(e)
        if "Unsupported invoice type" in msg:
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=500, detail=msg)

@app.get("/api/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    """Get user profile including configuration"""
    try:
        user_id = verify_user_token(authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        db_service = SupabaseDBService()
        profile = db_service.get_user_profile(user_id)
        
        if not profile:
            return {"id": user_id, "email": None, "target_sheet_id": None, "monthly_limit": 100}
        
        return {
            "id": profile.get("id"),
            "email": profile.get("email"),
            "target_sheet_id": profile.get("target_sheet_id"),
            "monthly_limit": profile.get("monthly_limit", 100)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profile/sheet-id")
async def update_sheet_id(
    sheet_id: dict,
    authorization: Optional[str] = Header(None)
):
    """Update user's target Google Sheet ID"""
    try:
        user_id = verify_user_token(authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        db_service = SupabaseDBService()
        
        # Get user email from utilisateurs if needed
        profile = db_service.get_user_profile(user_id)
        user_email = profile.get("email") if profile else None

        normalized_sheet_id = normalize_google_sheet_id(sheet_id.get("sheet_id"))
        
        # Update profile using Supabase client directly (upsert)
        db_service.client.table("invoicetosheet_profiles").upsert({
            "id": user_id,
            "email": user_email,
            "target_sheet_id": normalized_sheet_id
        }).execute()
        
        return {"success": True, "sheet_id": normalized_sheet_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile/refresh-token")
async def save_refresh_token(
    token_data: dict,
    authorization: Optional[str] = Header(None)
):
    """Save Google OAuth refresh token after authentication"""
    try:
        print(f"[DEBUG] refresh-token: authorization={authorization[:50] if authorization else None}...")
        print(f"[DEBUG] refresh-token: has_refresh_token={bool(token_data.get('refresh_token'))}")
        
        user_id = verify_user_token(authorization)
        print(f"[DEBUG] refresh-token: user_id={user_id}")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        print(f"[DEBUG] refresh-token: Creating SupabaseDBService...")
        db_service = SupabaseDBService()
        print(f"[DEBUG] refresh-token: SupabaseDBService created successfully")
        
        print(f"[DEBUG] refresh-token: Upserting profile...")
        db_service.client.table("invoicetosheet_profiles").upsert({
            "id": user_id,
            "google_refresh_token": token_data.get("refresh_token"),
            "email": token_data.get("email")
        }).execute()
        print(f"[DEBUG] refresh-token: Profile upserted successfully")
        
        return {"success": True}
    except Exception as e:
        print(f"[ERROR] save_refresh_token: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/usage")
async def get_usage(authorization: Optional[str] = Header(None)):
    """Get user's usage statistics"""
    try:
        user_id = verify_user_token(authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        db_service = SupabaseDBService()
        
        # Get usage statistics
        current_usage, monthly_limit = db_service.check_monthly_usage_limit(user_id)
        
        # Get failed count (separate query)
        from datetime import datetime
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        failed_response = db_service.client.table("invoicetosheet_usage_logs").select("id").eq(
            "user_id", user_id
        ).eq("status", "failed").gte("created_at", start_of_month.isoformat()).execute()
        
        failed = len(failed_response.data) if failed_response.data else 0
        
        return {
            "monthly_limit": monthly_limit,
            "current_usage": current_usage,
            "failed": failed,
            "remaining": monthly_limit - current_usage
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

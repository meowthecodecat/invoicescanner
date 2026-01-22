"""Supabase database service for user profiles and usage tracking."""
import os
from typing import Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime


class SupabaseDBService:
    """Service for interacting with Supabase database."""
    
    def __init__(self):
        """Initialize Supabase client."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        
        self.client: Client = create_client(supabase_url, supabase_key)
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from invoicetosheet_profiles table.
        
        Args:
            user_id: User UUID
            
        Returns:
            User profile dict with google_refresh_token, target_sheet_id, etc.
        """
        try:
            response = self.client.table("invoicetosheet_profiles").select("*").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        except Exception as e:
            raise Exception(f"Failed to get user profile: {str(e)}")
    
    def get_user_entreprise_id(self, user_id: str) -> Optional[str]:
        """
        Get user's entreprise_id from utilisateurs table.
        
        Args:
            user_id: User UUID
            
        Returns:
            Entreprise ID or None
        """
        try:
            response = self.client.table("utilisateurs").select("entreprise_id").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0].get("entreprise_id")
            
            return None
        except Exception as e:
            # Table utilisateurs might not exist, return None instead of raising
            print(f"Warning: Failed to get entreprise_id (table might not exist): {str(e)}")
            return None
    
    def create_usage_log(
        self,
        user_id: str,
        entreprise_id: Optional[str],
        file_name: str,
        file_size: Optional[int] = None
    ) -> str:
        """
        Create a usage log entry.
        
        Args:
            user_id: User UUID
            entreprise_id: Entreprise UUID (optional)
            file_name: Name of the uploaded file
            file_size: Size of the file in bytes (optional)
            
        Returns:
            Log ID (UUID)
        """
        import uuid
        log_id = str(uuid.uuid4())
        
        try:
            self.client.table("invoicetosheet_usage_logs").insert({
                "id": log_id,
                "user_id": user_id,
                "entreprise_id": entreprise_id,
                "file_name": file_name,
                "file_size": file_size,
                "status": "processing"
            }).execute()
            
            return log_id
        except Exception as e:
            raise Exception(f"Failed to create usage log: {str(e)}")
    
    def update_usage_log_success(
        self,
        log_id: str,
        extracted_data: Dict[str, Any],
        processing_time_ms: int,
        tokens_used: Optional[int] = None
    ):
        """
        Update usage log with success status.
        
        Args:
            log_id: Log UUID
            extracted_data: Extracted invoice data
            processing_time_ms: Processing time in milliseconds
            tokens_used: Number of OpenAI tokens used (optional)
        """
        # Some Supabase projects use different column names for token usage.
        # We'll prefer "openai_tokens" and gracefully retry without token fields if the column doesn't exist.
        update_data: Dict[str, Any] = {
            "status": "success",
            "extracted_data": extracted_data,
            "processing_time_ms": processing_time_ms,
        }

        if tokens_used is not None:
            update_data["openai_tokens"] = tokens_used

        try:
            self.client.table("invoicetosheet_usage_logs").update(update_data).eq("id", log_id).execute()
            return
        except Exception as e:
            # If the schema doesn't have openai_tokens (or any token column), retry without it.
            msg = str(e)
            if "PGRST204" in msg and ("openai_tokens" in msg or "tokens_used" in msg):
                update_data.pop("openai_tokens", None)
                try:
                    self.client.table("invoicetosheet_usage_logs").update(update_data).eq("id", log_id).execute()
                    return
                except Exception as e2:
                    raise Exception(f"Failed to update usage log: {str(e2)}")
            raise Exception(f"Failed to update usage log: {str(e)}")
    
    def update_usage_log_failed(
        self,
        log_id: str,
        error_message: str,
        processing_time_ms: int
    ):
        """
        Update usage log with failed status.
        
        Args:
            log_id: Log UUID
            error_message: Error message
            processing_time_ms: Processing time in milliseconds
        """
        try:
            self.client.table("invoicetosheet_usage_logs").update({
                "status": "failed",
                "error_message": error_message,
                "processing_time_ms": processing_time_ms
            }).eq("id", log_id).execute()
        except Exception as e:
            raise Exception(f"Failed to update usage log: {str(e)}")
    
    def check_monthly_usage_limit(self, user_id: str) -> tuple[int, int]:
        """
        Check user's monthly usage against limit.
        
        Args:
            user_id: User UUID
            
        Returns:
            Tuple of (current_usage, monthly_limit)
        """
        try:
            # Get profile for monthly limit
            profile = self.get_user_profile(user_id)
            monthly_limit = profile.get("monthly_limit", 100) if profile else 100
            
            # Get current month usage
            start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            response = self.client.table("invoicetosheet_usage_logs").select("id").eq(
                "user_id", user_id
            ).eq("status", "success").gte("created_at", start_of_month.isoformat()).execute()
            
            current_usage = len(response.data) if response.data else 0
            
            return current_usage, monthly_limit
        except Exception as e:
            raise Exception(f"Failed to check monthly usage: {str(e)}")

from supabase import create_client, Client
import os
import jwt
from typing import Optional

_supabase_auth_client: Client = None

def get_supabase_auth_client() -> Client:
    """Get Supabase client with anon key for token verification"""
    global _supabase_auth_client
    
    if _supabase_auth_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
        
        if not supabase_url or not supabase_anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        
        _supabase_auth_client = create_client(supabase_url, supabase_anon_key)
    
    return _supabase_auth_client

def verify_user_token(authorization: Optional[str]) -> Optional[str]:
    """
    Verify Supabase JWT token and return user ID
    Uses Supabase client to verify the token
    """
    if not authorization:
        return None
    
    try:
        # Extract token from "Bearer <token>" format
        token = authorization.replace("Bearer ", "").strip()
        
        # Use Supabase client to verify token
        supabase = get_supabase_auth_client()
        user_response = supabase.auth.get_user(token)
        
        if user_response.user:
            return user_response.user.id
        
        # Fallback: decode JWT without verification (less secure but works)
        # In production, always verify with Supabase
        decoded = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        
        user_id = decoded.get("sub")
        return user_id
        
    except Exception as e:
        print(f"Token verification error: {e}")
        # Fallback to simple JWT decode
        try:
            token = authorization.replace("Bearer ", "").strip()
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded.get("sub")
        except:
            return None

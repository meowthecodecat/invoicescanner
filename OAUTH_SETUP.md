# Google OAuth Setup Guide

## Important Note on Refresh Token Storage

Supabase handles OAuth tokens internally, but accessing the Google OAuth refresh token requires special handling. The refresh token is needed for background access to Google Sheets.

## Method 1: Using Supabase Database Hook (Recommended)

Create a database function to capture refresh tokens:

```sql
CREATE OR REPLACE FUNCTION public.handle_oauth_token()
RETURNS TRIGGER AS $$
BEGIN
  -- Extract refresh token from auth.users.raw_app_meta_data
  -- This depends on Supabase's internal structure
  IF NEW.raw_app_meta_data ? 'provider_refresh_token' THEN
    INSERT INTO public.user_profiles (id, email, google_refresh_token)
    VALUES (
      NEW.id,
      NEW.email,
      NEW.raw_app_meta_data->>'provider_refresh_token'
    )
    ON CONFLICT (id) 
    DO UPDATE SET 
      google_refresh_token = EXCLUDED.google_refresh_token,
      email = EXCLUDED.email;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger
CREATE TRIGGER on_auth_user_created
  AFTER INSERT OR UPDATE ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_oauth_token();
```

## Method 2: Client-Side Token Extraction

In some Supabase versions, you can access tokens from the session. Update `frontend/src/contexts/AuthContext.jsx`:

```javascript
const handleOAuthCallback = async (session) => {
  try {
    // Try different locations for refresh token
    let refreshToken = 
      session.provider_refresh_token ||
      session.identities?.[0]?.identity_data?.provider_refresh_token ||
      session.user?.app_metadata?.provider_refresh_token;
    
    // If not in session, try fetching from Supabase directly
    if (!refreshToken) {
      const { data } = await supabase
        .from('auth.users')
        .select('raw_app_meta_data')
        .eq('id', session.user.id)
        .single();
      
      refreshToken = data?.raw_app_meta_data?.provider_refresh_token;
    }
    
    if (refreshToken && session.user?.email) {
      const { saveRefreshToken } = await import('../lib/api');
      await saveRefreshToken(refreshToken, session.user.email);
    }
  } catch (error) {
    console.error('Error saving refresh token:', error);
  }
};
```

## Method 3: Manual Token Entry (Fallback)

If automatic extraction fails, provide a manual way for users to enter their refresh token. This is not ideal but works as a fallback.

## Verification

To verify tokens are being saved:
1. Check `user_profiles` table in Supabase
2. Verify `google_refresh_token` column has values
3. Test Google Sheets write functionality

## Google Cloud Console Setup

1. Create OAuth 2.0 credentials
2. Authorized redirect URIs must include:
   - `https://<project-ref>.supabase.co/auth/v1/callback`
   - Your frontend URL for local dev: `http://localhost:3000`

## Scopes Required

- `https://www.googleapis.com/auth/spreadsheets` - Read/write Google Sheets
- `https://www.googleapis.com/auth/drive.file` - Access to files created by app

Make sure these scopes are requested in the OAuth flow.

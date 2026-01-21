-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- User Profiles Table
-- Stores user-specific configuration including Google OAuth tokens and Sheet ID
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    google_refresh_token TEXT,
    target_sheet_id TEXT,
    monthly_limit INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Usage Logs Table
-- Tracks all processing operations for billing and analytics
CREATE TABLE IF NOT EXISTS usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_size BIGINT,
    status TEXT NOT NULL, -- 'success', 'failed', 'processing'
    extracted_data JSONB,
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_status ON usage_logs(status);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to update updated_at on user_profiles
CREATE TRIGGER update_user_profiles_updated_at 
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to capture Google OAuth refresh token from auth.users
CREATE OR REPLACE FUNCTION public.handle_oauth_token()
RETURNS TRIGGER AS $$
BEGIN
  -- Extract refresh token from auth.users.raw_app_meta_data
  -- Supabase stores OAuth tokens in raw_app_meta_data
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
      email = EXCLUDED.email,
      updated_at = NOW();
  ELSIF NEW.raw_app_meta_data ? 'provider' AND NEW.raw_app_meta_data->>'provider' = 'google' THEN
    -- Fallback: check if there's a token stored differently
    INSERT INTO public.user_profiles (id, email)
    VALUES (NEW.id, NEW.email)
    ON CONFLICT (id) 
    DO UPDATE SET 
      email = EXCLUDED.email,
      updated_at = NOW();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger to capture OAuth tokens on user creation/update
CREATE TRIGGER on_auth_user_oauth
  AFTER INSERT OR UPDATE ON auth.users
  FOR EACH ROW
  WHEN (NEW.raw_app_meta_data ? 'provider_refresh_token' OR NEW.raw_app_meta_data->>'provider' = 'google')
  EXECUTE FUNCTION public.handle_oauth_token();

-- Row Level Security (RLS) Policies
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view and update their own profile
CREATE POLICY "Users can view own profile"
    ON user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Policy: Users can view their own usage logs
CREATE POLICY "Users can view own usage logs"
    ON usage_logs FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Service role can manage all data (for backend operations)
CREATE POLICY "Service role full access"
    ON user_profiles FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role full access logs"
    ON usage_logs FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

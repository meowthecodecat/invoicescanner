-- Schema spécifique pour InvoiceToSheet AI
-- Intégration avec la structure existante

-- Enable UUID extension (si pas déjà fait)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table pour les profils utilisateurs InvoiceToSheet AI
-- Utilise la table utilisateurs existante
CREATE TABLE IF NOT EXISTS invoicetosheet_profiles (
    id UUID PRIMARY KEY REFERENCES utilisateurs(id) ON DELETE CASCADE,
    email TEXT,
    google_refresh_token TEXT,
    target_sheet_id TEXT,
    monthly_limit INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table pour les logs d'utilisation InvoiceToSheet AI
CREATE TABLE IF NOT EXISTS invoicetosheet_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES utilisateurs(id) ON DELETE CASCADE,
    entreprise_id UUID REFERENCES entreprises(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_size BIGINT,
    status TEXT NOT NULL, -- 'success', 'failed', 'processing'
    extracted_data JSONB,
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes pour performance
CREATE INDEX IF NOT EXISTS idx_invoicetosheet_usage_logs_user_id 
    ON invoicetosheet_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_invoicetosheet_usage_logs_entreprise_id 
    ON invoicetosheet_usage_logs(entreprise_id);
CREATE INDEX IF NOT EXISTS idx_invoicetosheet_usage_logs_created_at 
    ON invoicetosheet_usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_invoicetosheet_usage_logs_status 
    ON invoicetosheet_usage_logs(status);

-- Fonction pour mettre à jour updated_at
CREATE OR REPLACE FUNCTION update_invoicetosheet_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger pour updated_at
CREATE TRIGGER update_invoicetosheet_profiles_updated_at 
    BEFORE UPDATE ON invoicetosheet_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_invoicetosheet_updated_at_column();

-- Row Level Security (RLS) Policies
ALTER TABLE invoicetosheet_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoicetosheet_usage_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view and update their own profile
CREATE POLICY "Users can view own invoicetosheet profile"
    ON invoicetosheet_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own invoicetosheet profile"
    ON invoicetosheet_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own invoicetosheet profile"
    ON invoicetosheet_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Policy: Users can view their own usage logs
CREATE POLICY "Users can view own invoicetosheet usage logs"
    ON invoicetosheet_usage_logs FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Service role can manage all data (for backend operations)
CREATE POLICY "Service role full access invoicetosheet profiles"
    ON invoicetosheet_profiles FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role full access invoicetosheet logs"
    ON invoicetosheet_usage_logs FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Fonction pour capturer le refresh token Google OAuth depuis auth.users
-- Note: Supabase stocke les tokens OAuth dans auth.users.raw_app_meta_data
CREATE OR REPLACE FUNCTION public.handle_invoicetosheet_oauth_token()
RETURNS TRIGGER AS $$
BEGIN
  -- Extraire le refresh token depuis raw_app_meta_data
  IF NEW.raw_app_meta_data ? 'provider_refresh_token' THEN
    INSERT INTO public.invoicetosheet_profiles (id, email, google_refresh_token)
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
    -- Fallback: créer le profil même sans refresh token
    INSERT INTO public.invoicetosheet_profiles (id, email)
    VALUES (NEW.id, NEW.email)
    ON CONFLICT (id) 
    DO UPDATE SET 
      email = EXCLUDED.email,
      updated_at = NOW();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger pour capturer les tokens OAuth sur création/mise à jour d'utilisateur
DROP TRIGGER IF EXISTS on_auth_user_invoicetosheet_oauth ON auth.users;
CREATE TRIGGER on_auth_user_invoicetosheet_oauth
  AFTER INSERT OR UPDATE ON auth.users
  FOR EACH ROW
  WHEN (
    NEW.raw_app_meta_data ? 'provider_refresh_token' 
    OR (NEW.raw_app_meta_data ? 'provider' AND NEW.raw_app_meta_data->>'provider' = 'google')
  )
  EXECUTE FUNCTION public.handle_invoicetosheet_oauth_token();

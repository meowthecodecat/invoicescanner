# Quick Start Guide

## 1. Prerequisites Setup

### Supabase
1. Create account at https://supabase.com
2. Create a new project
3. Run SQL from `supabase/schema.sql` in SQL Editor

### Google Cloud Console
1. Create project at https://console.cloud.google.com
2. Enable Google Drive API and Google Sheets API
3. Create OAuth 2.0 credentials (Web application)
4. Add redirect URI: `https://<your-project>.supabase.co/auth/v1/callback`

### OpenAI
1. Get API key from https://platform.openai.com
2. Ensure access to GPT-4o-mini model

## 2. Configure Supabase

### Enable Google OAuth
1. Go to Authentication > Providers
2. Enable Google provider
3. Add Client ID and Client Secret from Google Cloud Console
4. Save

### Set Redirect URL
In Google OAuth settings, add:
- `https://<your-project>.supabase.co/auth/v1/callback`

## 3. Environment Setup

### Root `.env` file
```bash
cp config.example.env .env
# Edit .env with your credentials
```

### Frontend `.env` file
```bash
cd frontend
cp .env.example .env
# Edit .env with your Supabase credentials
```

## 4. Run Locally

### Option A: Docker Compose (Recommended)
```bash
docker-compose up -d
```

Access:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Prometheus: http://localhost:9090

### Option B: Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 5. First Use

1. Open http://localhost:3000
2. Click "Sign in with Google"
3. Grant permissions for Drive and Sheets
4. Enter your Google Sheet ID in the dashboard
5. Drag and drop an invoice file
6. Check your Google Sheet for extracted data

## 6. Verify Setup

- ✅ User profile created in `user_profiles` table
- ✅ Google refresh token captured (check `google_refresh_token` column)
- ✅ Sheet ID saved in profile
- ✅ Usage logs appearing in `usage_logs` table
- ✅ Prometheus metrics available at `/metrics`

## Troubleshooting

**OAuth not working:**
- Check redirect URLs match exactly
- Verify Google OAuth is enabled in Supabase
- Check browser console for errors

**Refresh token not saving:**
- Check database trigger is created
- Manually verify in `auth.users.raw_app_meta_data`
- See OAUTH_SETUP.md for alternatives

**Invoice processing fails:**
- Verify OpenAI API key is valid
- Check Google Sheets API is enabled
- Verify Sheet ID is correct
- Check usage limits haven't been reached

## Production Deployment

1. Update environment variables for production
2. Set `FRONTEND_URL` to your production domain
3. Update Google OAuth redirect URIs
4. Deploy to DigitalOcean or your preferred platform
5. Run `docker-compose up -d`

For detailed setup, see SETUP.md

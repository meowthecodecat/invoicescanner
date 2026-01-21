# Setup Guide for InvoiceToSheet AI

## Prerequisites

1. **Supabase Account**
   - Create a project at https://supabase.com
   - Enable Google OAuth provider in Authentication > Providers
   - Configure OAuth redirect URL: `http://localhost:3000/dashboard`

2. **Google Cloud Console**
   - Create a project at https://console.cloud.google.com
   - Enable Google Drive API and Google Sheets API
   - Create OAuth 2.0 credentials (Web application)
   - Add authorized redirect URIs:
     - `https://<your-supabase-project>.supabase.co/auth/v1/callback`
     - `http://localhost:3000/dashboard`

3. **OpenAI API Key**
   - Sign up at https://platform.openai.com
   - Generate an API key with GPT-4o-mini access

## Database Setup

1. Open your Supabase project dashboard
2. Go to SQL Editor
3. Run the SQL schema from `supabase/invoicetosheet_schema.sql`
4. This will create:
   - `invoicetosheet_profiles` table (linked to existing `utilisateurs` table)
   - `invoicetosheet_usage_logs` table (linked to `utilisateurs` and `entreprises`)
   - Required indexes and RLS policies
   - Automatic OAuth token capture trigger

**Note:** This integrates with your existing database structure. The tables use your existing `utilisateurs` and `entreprises` tables.

## Environment Variables

Create a `.env` file in the root directory:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# OpenAI Configuration
OPENAI_API_KEY=sk-...

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
REDIRECT_URI=http://localhost:3000/auth/callback

# Billing Configuration
MONTHLY_LIMIT=100

# Frontend URL (for production)
FRONTEND_URL=http://localhost:3000
```

For the frontend, create `frontend/.env`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend will run on http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will run on http://localhost:3000

## Docker Deployment

### Build and Run

```bash
docker-compose up -d
```

### Services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Prometheus Metrics**: http://localhost:9090

### View Logs

```bash
docker-compose logs -f
```

### Stop Services

```bash
docker-compose down
```

## DigitalOcean Deployment

1. Create a Docker Droplet on DigitalOcean
2. Clone this repository
3. Copy `.env` file with production values
4. Update `docker-compose.yml` if needed
5. Run `docker-compose up -d`

## Configuration

### Google OAuth Setup in Supabase

1. Go to Authentication > Providers > Google
2. Enable Google provider
3. Add Client ID and Client Secret from Google Cloud Console
4. Set redirect URL to your frontend URL

### Usage Limits

Default monthly limit is 100 invoices per user. This can be:
- Changed per user in the `user_profiles.monthly_limit` column
- Changed globally via `MONTHLY_LIMIT` environment variable

## Monitoring

Prometheus metrics are available at `/metrics` endpoint:
- `supabase_db_calls_total`: Total database calls by operation and table
- `invoice_processing_time_seconds`: Processing time histogram

## Troubleshooting

### Google OAuth Not Working
- Verify redirect URLs match exactly
- Check that Google OAuth is enabled in Supabase
- Ensure scopes include Drive and Sheets permissions

### Token Verification Failed
- Check that `SUPABASE_ANON_KEY` is set in backend
- Verify JWT token is being passed correctly in Authorization header

### OpenAI Errors
- Verify API key is valid and has credits
- Check model access (gpt-4o-mini)

### Google Sheets Write Failures
- Verify refresh token is saved correctly
- Check that Sheet ID is correct
- Ensure Google Sheets API is enabled

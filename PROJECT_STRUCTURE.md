# InvoiceToSheet AI - Project Structure

## Overview

Complete SaaS application for automated invoice processing with AI extraction and Google Sheets integration.

## Directory Structure

```
.
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI application and routes
│   │   ├── auth.py         # JWT token verification
│   │   ├── database.py     # Supabase client management
│   │   ├── processor.py    # Invoice processing with OpenAI
│   │   ├── metrics.py      # Prometheus metrics
│   │   └── worker.py       # Background worker (placeholder)
│   ├── Dockerfile          # Backend container definition
│   └── requirements.txt    # Python dependencies
│
├── frontend/               # React frontend application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Login.jsx   # Google OAuth login
│   │   │   ├── Dashboard.jsx # Main user interface
│   │   │   └── ProtectedRoute.jsx # Route protection
│   │   ├── contexts/
│   │   │   └── AuthContext.jsx # Authentication context
│   │   ├── lib/
│   │   │   ├── supabase.js # Supabase client
│   │   │   └── api.js      # API client
│   │   ├── App.jsx         # Root component
│   │   └── main.jsx        # Entry point
│   ├── Dockerfile          # Frontend container definition
│   ├── nginx.conf          # Nginx configuration
│   └── package.json        # Node dependencies
│
├── supabase/
│   └── schema.sql          # Database schema and migrations
│
├── prometheus/
│   └── prometheus.yml      # Prometheus configuration
│
├── docker-compose.yml      # Multi-container orchestration
├── config.example.env      # Environment variables template
├── README.md               # Project overview
├── SETUP.md                # Setup instructions
├── OAUTH_SETUP.md          # OAuth configuration guide
└── .gitignore              # Git ignore rules
```

## Key Components

### Backend (FastAPI)

**API Endpoints:**
- `POST /api/process-invoice` - Process uploaded invoice
- `GET /api/profile` - Get user profile
- `PUT /api/profile/sheet-id` - Update Sheet ID
- `POST /api/profile/refresh-token` - Save Google refresh token
- `GET /api/usage` - Get usage statistics
- `GET /metrics` - Prometheus metrics endpoint

**Core Modules:**
- `processor.py`: OpenAI integration for invoice extraction
- `auth.py`: JWT token verification with Supabase
- `database.py`: Supabase client singleton
- `metrics.py`: Prometheus metrics (including `supabase_db_calls_total`)

### Frontend (React)

**Pages:**
- Login: Google OAuth authentication
- Dashboard: Invoice upload, configuration, usage stats

**Features:**
- Drag & drop file upload
- Real-time usage tracking
- Google Sheet ID configuration
- Protected routes with authentication

### Database (Supabase PostgreSQL)

**Tables:**
- `user_profiles`: User configuration and OAuth tokens
- `usage_logs`: Processing history and billing data

**Triggers:**
- Auto-capture OAuth refresh tokens from auth.users
- Auto-update timestamps

### Infrastructure

**Docker Services:**
- `web`: React frontend (Nginx)
- `backend`: FastAPI application
- `worker`: Background processing (placeholder)
- `prometheus`: Metrics collection

## Technology Stack

- **Frontend**: React 18, Vite, Supabase Auth
- **Backend**: FastAPI, Python 3.11
- **Database**: Supabase (PostgreSQL)
- **AI**: OpenAI GPT-4o-mini (JSON Mode)
- **Storage**: Google Sheets API
- **Monitoring**: Prometheus
- **Containerization**: Docker Compose

## Data Flow

1. User authenticates via Supabase (Google OAuth)
2. OAuth refresh token captured via database trigger
3. User configures target Google Sheet ID
4. User uploads invoice (drag & drop)
5. FastAPI receives file, extracts data with OpenAI
6. Data written to Google Sheets using refresh token
7. Usage logged to Supabase
8. Monthly limits checked before processing

## Security

- JWT token verification for all API requests
- Row Level Security (RLS) on Supabase tables
- Service role key for backend operations
- Environment variables for sensitive data
- CORS configuration for frontend access

## Monitoring

- Prometheus metrics endpoint (`/metrics`)
- Custom metric: `supabase_db_calls_total`
- Processing time histograms
- Usage tracking in database

## Next Steps

1. Set up Supabase project and run schema.sql
2. Configure Google OAuth in Supabase
3. Set environment variables
4. Build and deploy with Docker Compose
5. Test invoice processing flow

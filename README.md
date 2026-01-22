# InvoiceToSheet AI

A standalone SaaS tool that extracts invoice data using AI and automatically populates Google Sheets.

## Architecture

- **Frontend**: React + Supabase Auth (Google Provider)
- **Backend**: FastAPI (Python) - Processing Engine
- **Database**: Supabase (PostgreSQL)
- **Extraction**: Local OCR (Tesseract) by default, OpenAI optional
- **Infrastructure**: Docker Compose for DigitalOcean

## Features

1. Google OAuth authentication via Supabase
2. Invoice upload with drag & drop
3. AI-powered invoice data extraction
4. Automatic Google Sheets population
5. Usage tracking and billing limits
6. Prometheus metrics monitoring

## Setup

### Prerequisites

- Docker and Docker Compose
- Supabase project with Google OAuth configured
- Google Cloud project with Sheets API enabled
- **Optional**: OpenAI API key (only if using `EXTRACTION_BACKEND=openai`)
- **Local dev (Windows)**: Tesseract OCR installed (see below)

### Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

### Database Setup

Run the SQL schema in your Supabase SQL editor (see `supabase/invoicetosheet_schema.sql`)

**Note:** This integrates with your existing database structure (`utilisateurs`, `entreprises`). See `MIGRATION_GUIDE.md` for details.

### Run with Docker Compose

```bash
docker-compose up -d
```

### Development

#### Frontend
```bash
cd frontend
npm install
npm start
```

#### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Note for Windows dev**: If using OCR mode (default), install Tesseract:
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Or via Chocolatey: `choco install tesseract -y`
- Add to `.env`: `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

**Production (Docker)**: Tesseract is automatically installed in the Docker image.

## Project Structure

```
.
├── frontend/          # React application
├── backend/           # FastAPI application
├── supabase/          # Database schemas
├── docker-compose.yml
└── README.md
```

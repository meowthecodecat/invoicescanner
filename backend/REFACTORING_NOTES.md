# Refactoring Notes - Supabase Integration

## Overview

The project has been refactored to use a modular service architecture with Supabase integration.

## Architecture Changes

### New Service Structure

```
backend/app/
├── services/
│   ├── __init__.py
│   ├── supabase_db.py      # Database operations (profiles, usage logs)
│   ├── ai.py               # OpenAI invoice extraction
│   └── google_sheets.py     # Google Sheets operations with dynamic tabs
├── processor.py            # Main processing pipeline (refactored)
└── main.py                 # FastAPI endpoints (refactored)
```

## Key Changes

### 1. Supabase Integration (`services/supabase_db.py`)

- **Replaced**: Direct Supabase client calls in main.py
- **New**: `SupabaseDBService` class with methods:
  - `get_user_profile()` - Fetch user profile with refresh token and sheet ID
  - `get_user_entreprise_id()` - Get user's entreprise ID
  - `create_usage_log()` - Create usage tracking entry
  - `update_usage_log_success()` - Update log with success and token usage
  - `update_usage_log_failed()` - Update log with error
  - `check_monthly_usage_limit()` - Check usage against monthly limit

### 2. AI Service (`services/ai.py`)

- **Replaced**: OpenAI logic embedded in processor
- **New**: `AIService` class with:
  - `extract_invoice_data()` - Extracts invoice data and returns usage info
  - Returns tuple: `(extracted_data, usage_info)` where usage_info contains token counts

### 3. Google Sheets Service (`services/google_sheets.py`)

- **Replaced**: Direct Google Sheets API calls in processor
- **New**: `GoogleSheetsService` class with:
  - **Dynamic Tab Creation**: Creates new tab per run with naming `Run_YYYY-MM-DD_HHmm`
  - `get_or_create_run_tab()` - Creates tab if it doesn't exist, adds headers
  - `write_invoice_data()` - Writes invoice data to new run tab
  - **Future-ready**: Commented method for monthly tabs (`get_or_create_monthly_tab()`)

### 4. Processor Refactoring (`processor.py`)

**Before:**
- Mixed concerns (AI, Sheets, DB)
- Direct Supabase client usage
- Embedded OpenAI logic

**After:**
- Clean separation of concerns
- Uses service classes
- Simplified flow:
  1. Read file
  2. Extract with AI service
  3. Write to Sheets (auto-creates tab)
  4. Update usage log

### 5. Main API Refactoring (`main.py`)

**Changes:**
- Uses `SupabaseDBService` instead of direct client
- Simplified error handling
- Cleaner code structure

## Task Execution Flow

```
1. User uploads invoice
   ↓
2. Verify authentication (Supabase JWT)
   ↓
3. Get user profile from Supabase (google_refresh_token, target_sheet_id)
   ↓
4. Check monthly usage limit
   ↓
5. Create usage log entry
   ↓
6. Process invoice:
   a. Extract data with OpenAI (AI Service)
   b. Refresh Google access token (Google Sheets Service)
   c. Create new run tab (Run_YYYY-MM-DD_HHmm)
   d. Write invoice data to tab
   ↓
7. Update usage log with success + token usage
```

## Environment Variables

**Required:**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key for backend operations
- `OPENAI_API_KEY` - OpenAI API key
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret

**Optional:**
- `OPENAI_MODEL` - Defaults to `gpt-4o-mini`
- `SUPABASE_ANON_KEY` - For token verification (optional)

## Database Schema

The code expects the following Supabase tables:

1. **invoicetosheet_profiles**
   - `id` (UUID, references utilisateurs.id)
   - `email` (TEXT)
   - `google_refresh_token` (TEXT)
   - `target_sheet_id` (TEXT) - Google Spreadsheet ID
   - `monthly_limit` (INTEGER, default 100)

2. **invoicetosheet_usage_logs**
   - `id` (UUID)
   - `user_id` (UUID, references utilisateurs.id)
   - `entreprise_id` (UUID, references entreprises.id)
   - `file_name` (TEXT)
   - `file_size` (BIGINT)
   - `status` (TEXT: 'processing', 'success', 'failed')
   - `extracted_data` (JSONB)
   - `error_message` (TEXT)
   - `processing_time_ms` (INTEGER)
   - `tokens_used` (INTEGER) - OpenAI tokens used
   - `created_at` (TIMESTAMP)

## Testing Mode: Run-Based Tabs

Currently, the system creates a **new tab for every processing run**:
- Tab naming: `Run_YYYY-MM-DD_HHmm` (e.g., `Run_2024-01-15_1430`)
- Each run gets its own tab
- Headers are automatically added: `["Shop Name", "Date", "Total HT", "Total TTC", "VAT", "Items"]`

### Switching to Monthly Tabs

To switch to monthly tabs, modify `services/google_sheets.py`:

1. Uncomment `get_or_create_monthly_tab()` method
2. Update `write_invoice_data()` to use monthly tab instead of run tab
3. Tab naming will be: `Factures_MM_YYYY` (e.g., `Factures_01_2024`)

## Benefits of Refactoring

1. **Modularity**: Each service has a single responsibility
2. **Testability**: Services can be tested independently
3. **Maintainability**: Easier to update individual components
4. **Scalability**: Services can be extended without affecting others
5. **Clean Code**: Separation of concerns, better readability

## Migration Notes

- All existing functionality preserved
- No breaking changes to API endpoints
- Database schema remains the same
- Environment variables updated (see `config.example.env`)

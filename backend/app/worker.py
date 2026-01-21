"""
Background worker for processing invoices asynchronously
This can be extended to handle queued jobs
"""
import asyncio
from app.database import get_supabase_client
from app.processor import InvoiceProcessor

async def process_queue():
    """Process queued invoice jobs"""
    # This is a placeholder for future async processing
    # For now, processing is done synchronously in the API endpoint
    pass

if __name__ == "__main__":
    asyncio.run(process_queue())

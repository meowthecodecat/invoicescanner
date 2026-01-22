"""Invoice processor using modular services."""
import os
import time
from typing import Dict, Any
from fastapi import UploadFile

from app.services.supabase_db import SupabaseDBService
from app.services.ai import AIService
from app.services.ocr import OCRService
from app.services.google_sheets import GoogleSheetsService


class InvoiceProcessor:
    """Main invoice processing pipeline using modular services."""
    
    def __init__(self, user_id: str, log_id: str):
        """
        Initialize invoice processor.
        
        Args:
            user_id: User UUID
            log_id: Usage log UUID
        """
        self.user_id = user_id
        self.log_id = log_id
        self.db_service = SupabaseDBService()
        # Switchable extraction backend:
        # - ocr (default): local OCR + heuristics (no OpenAI, no external APIs)
        # - openai: uses OpenAI vision/json (requires OPENAI_API_KEY)
        backend = (os.getenv("EXTRACTION_BACKEND", "ocr") or "ocr").strip().lower()
        self.extraction_backend = backend
        if backend == "openai":
            # Only initialize OpenAI if explicitly requested
            try:
                self.ai_service = AIService()
            except ValueError as e:
                raise Exception(f"OpenAI mode requires OPENAI_API_KEY: {str(e)}")
            self.ocr_service = None
        else:
            self.ai_service = None
            self.ocr_service = OCRService()
    
    async def process_invoice(self, file: UploadFile, refresh_token: str, sheet_id: str) -> Dict[str, Any]:
        """
        Main processing pipeline:
        1. Read file content
        2. Extract invoice data using AI
        3. Write to Google Sheets (creates new run tab)
        4. Update usage log with success
        
        Args:
            file: Uploaded invoice file
            refresh_token: Google OAuth refresh token
            sheet_id: Target Google Spreadsheet ID
            
        Returns:
            Processing result with extracted data and metadata
        """
        start_time = time.time()
        
        try:
            # Read file content
            file_content = await file.read()
            
            # Step 1: Extract invoice data using selected backend
            if self.extraction_backend == "ocr":
                extracted_data, usage_info = self.ocr_service.extract_invoice_data(
                    file_content,
                    file.filename or "invoice",
                    getattr(file, "content_type", None),
                )
            else:
                extracted_data, usage_info = self.ai_service.extract_invoice_data(
                    file_content,
                    file.filename or "invoice",
                    getattr(file, "content_type", None),
                )
            
            # Step 2: Write to Google Sheets (creates new run tab automatically)
            sheets_service = GoogleSheetsService(refresh_token=refresh_token)
            tab_name = sheets_service.write_invoice_data(sheet_id, extracted_data)
            
            # Step 3: Update usage log with success
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.db_service.update_usage_log_success(
                log_id=self.log_id,
                extracted_data=extracted_data,
                processing_time_ms=processing_time_ms,
                tokens_used=usage_info.get("total_tokens")
            )
            
            return {
                "success": True,
                "data": extracted_data,
                "processing_time_ms": processing_time_ms,
                "tab_name": tab_name,
                "tokens_used": usage_info.get("total_tokens"),
                "extraction_backend": self.extraction_backend,
            }
            
        except Exception as e:
            # Update usage log with failure
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.db_service.update_usage_log_failed(
                log_id=self.log_id,
                error_message=str(e),
                processing_time_ms=processing_time_ms
            )
            
            raise

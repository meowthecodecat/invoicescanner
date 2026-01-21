"""OpenAI service for invoice data extraction."""
import os
import json
import base64
from typing import Dict, Any
from openai import OpenAI


class AIService:
    """Service for extracting invoice data using OpenAI GPT-4o-mini."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    def extract_invoice_data(self, file_content: bytes, filename: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract invoice data from file using OpenAI.
        
        Args:
            file_content: File content as bytes
            filename: Name of the file
            
        Returns:
            Tuple of (extracted_data, usage_info) where usage_info contains token counts
        """
        # Convert file to base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Determine file type
        file_type = self._get_file_type(filename)
        
        # Prepare system prompt for JSON mode
        system_prompt = """You are an expert invoice parser. Extract the following information from the invoice:
- shop_name: Name of the shop/vendor
- date: Invoice date (YYYY-MM-DD format)
- total_ht: Total excluding VAT (number)
- total_ttc: Total including VAT (number)
- vat: VAT amount (number)
- items: Array of items, each with: description, quantity, unit_price, total

Return ONLY valid JSON in this exact structure:
{
  "shop_name": "string",
  "date": "YYYY-MM-DD",
  "total_ht": number,
  "total_ttc": number,
  "vat": number,
  "items": [
    {
      "description": "string",
      "quantity": number,
      "unit_price": number,
      "total": number
    }
  ]
}"""
        
        user_prompt = f"""Analyze this invoice file ({filename}) and extract all relevant information. Return only the JSON object with no additional text."""
        
        try:
            if file_type == "image":
                # Use vision API for images
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{filename.split('.')[-1]};base64,{file_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0
                )
            else:
                # For text/PDF (assuming text extraction was done)
                # In production, you'd use a PDF parser or OCR service
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0
                )
            
            # Parse response
            result = response.choices[0].message.content
            extracted_data = json.loads(result)
            
            # Validate required fields
            required_fields = ["shop_name", "date", "total_ht", "total_ttc", "vat", "items"]
            for field in required_fields:
                if field not in extracted_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Extract usage information
            usage_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return extracted_data, usage_info
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to extract invoice data: {str(e)}")
    
    @staticmethod
    def _get_file_type(filename: str) -> str:
        """Determine file type from filename."""
        filename_lower = filename.lower()
        
        if filename_lower.endswith(('.png', '.jpg', '.jpeg')):
            return "image"
        elif filename_lower.endswith('.pdf'):
            return "pdf"
        else:
            return "text"

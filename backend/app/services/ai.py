"""OpenAI service for invoice data extraction using Vision API (100% AI, no OCR)."""

import os
import json
import base64
from typing import Dict, Any
from openai import OpenAI

try:
    import fitz  # PyMuPDF (only for PDF to image conversion)
except Exception:
    fitz = None


class AIService:
    """Service for extracting invoice data using OpenAI Vision API (100% AI, no OCR)."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set")
        
        self.client = OpenAI(api_key=api_key)
        # Use gpt-4o for better accuracy (gpt-4o-mini is too limited for complex invoice parsing)
        # Be robust to inline comments in .env
        self.model = (os.getenv("OPENAI_MODEL", "gpt-4o") or "gpt-4o").split("#", 1)[0].strip()

    @staticmethod
    def _get_file_type(filename: str, content_type: str | None = None) -> str:
        """Determine file type from content_type first, then filename."""
        ct = (content_type or "").lower().strip()
        if ct.startswith("image/"):
            return "image"
        if ct == "application/pdf":
            return "pdf"

        filename_lower = (filename or "").lower()
        if filename_lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return "image"
        if filename_lower.endswith(".pdf"):
            return "pdf"
        return "text"

    @staticmethod
    def _mime_from_filename(filename: str) -> str:
        """Get MIME type from filename."""
        ext = (filename.rsplit(".", 1)[-1] or "").lower()
        if ext in ("jpg", "jpeg"):
            return "image/jpeg"
        if ext == "png":
            return "image/png"
        if ext == "webp":
            return "image/webp"
        return "image/jpeg"  # Default

    @staticmethod
    def _pdf_to_png_pages_base64(pdf_bytes: bytes, max_pages: int = 3) -> list[str]:
        """
        Render PDF pages to PNG images and return base64 strings for OpenAI Vision API.
        Uses PyMuPDF (only dependency for PDF conversion).
        """
        if fitz is None:
            raise Exception("PDF support is not available (PyMuPDF not installed).")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            pages_b64: list[str] = []
            page_count = min(len(doc), max_pages)
            # Render at high DPI for best quality with Vision API
            mat = fitz.Matrix(2, 2)  # ~144 DPI (good quality, reasonable size)
            for i in range(page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes("png")
                pages_b64.append(base64.b64encode(png_bytes).decode("utf-8"))
            return pages_b64
        finally:
            doc.close()

    @staticmethod
    def _validate_and_clean_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process and validate extracted data to fix common errors."""
        # Reject country names as customer_name (more comprehensive list)
        country_names = {
            "france", "belgium", "belgique", "spain", "espagne", "italy", "italie", 
            "germany", "allemagne", "netherlands", "pays-bas", "uk", "united kingdom",
            "portugal", "suisse", "switzerland", "luxembourg", "autriche", "austria",
            "pologne", "poland", "roumanie", "romania", "hongrie", "hungary"
        }
        if data.get("customer_name"):
            customer_lower = data["customer_name"].lower().strip()
            # Check if it's exactly a country name or contains only country name
            if customer_lower in country_names or customer_lower.split()[0] in country_names:
                data["customer_name"] = None
        
        # Ensure shop_name is not the same as customer_name
        if data.get("shop_name") and data.get("customer_name"):
            if data["shop_name"].strip().lower() == data["customer_name"].strip().lower():
                # If they're the same, it's likely an error - prefer shop_name and clear customer_name
                data["customer_name"] = None
        
        # Fix document_type if it's clearly wrong (e.g., gas_station_ticket when it has "Fourni par")
        # This is a fallback - the prompt should handle it, but we validate here too
        if data.get("document_type") == "gas_station_ticket":
            # If it has invoice-like structure, it's probably an invoice
            # We can't check the text here, but we can validate based on other fields
            if data.get("shop_name") and data.get("customer_name") and data.get("invoice_number"):
                # Has structured invoice fields, likely an invoice
                data["document_type"] = "invoice"
        
        # Validate IBAN format
        if data.get("iban"):
            iban = data["iban"].replace(" ", "").upper()
            # French IBAN must be 27 chars
            if iban.startswith("FR") and len(iban) != 27:
                data["iban"] = None
            # Other IBANs: 15-34 chars
            elif not iban.startswith("FR") and (len(iban) < 15 or len(iban) > 34):
                data["iban"] = None
            # Must start with 2 letters + 2 digits
            elif len(iban) < 4 or not iban[:2].isalpha() or not iban[2:4].isdigit():
                data["iban"] = None
            else:
                data["iban"] = iban
        
        # Validate VAT number format
        if data.get("vat_number"):
            vat = data["vat_number"].replace(" ", "").upper()
            # Must start with 2 letters (country code)
            if len(vat) < 4 or not vat[:2].isalpha():
                data["vat_number"] = None
            # French VAT: FR + 2 digits + 9 alphanumeric (11 after FR) OR FR + 11 digits
            elif vat.startswith("FR"):
                if len(vat) != 13:  # FR (2) + 11 chars = 13 total
                    data["vat_number"] = None
                else:
                    data["vat_number"] = vat
            # Other countries: at least 4 chars (2 letters + 2+ alphanumeric)
            elif len(vat) < 4:
                data["vat_number"] = None
            else:
                data["vat_number"] = vat
        
        # Validate SIRET (14 digits) or SIREN (9 digits)
        if data.get("siret"):
            siret = data["siret"].replace(" ", "").replace("-", "")
            if not siret.isdigit():
                data["siret"] = None
            elif len(siret) not in [9, 14]:
                data["siret"] = None
            else:
                data["siret"] = siret
        
        # Ensure items is a list
        if not isinstance(data.get("items"), list):
            data["items"] = []
        
        # Ensure items is a list and validate item structure
        if not isinstance(data.get("items"), list):
            data["items"] = []
        
        # Filter out invalid items and ensure correct structure
        if data.get("items"):
            valid_items = []
            total_keywords = ("total", "totaux", "sous-total", "subtotal", "net a payer", "net à payer", "tva", "vat")
            header_keywords = ("description", "désignation", "quantité", "quantite", "quantity", "qty", "prix ht", "prix ttc", "montant", "tva", "vat")
            for item in data["items"]:
                if not isinstance(item, dict):
                    continue
                desc = (item.get("description") or "").lower().strip()
                # Skip if description is empty
                if not desc:
                    continue
                # Skip if it looks like a total line
                if any(kw in desc for kw in total_keywords):
                    continue
                # Skip if it looks like a table header
                if desc in header_keywords or (len(desc) < 3 and desc.isalpha()):
                    continue
                # Ensure description is meaningful (at least 2 characters)
                if len(desc) < 2:
                    continue
                
                # Ensure item has correct structure (map old field names to new ones if needed)
                cleaned_item = {
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity") or item.get("qty"),
                    "unit_price_ht": item.get("unit_price_ht") or item.get("unit_price"),
                    "total_ht": item.get("total_ht") or item.get("total"),
                    "vat_rate": item.get("vat_rate") or item.get("vat")
                }
                valid_items.append(cleaned_item)
            data["items"] = valid_items
        
        # Rename vat to vat_amount for consistency (if old field name exists)
        if "vat" in data and "vat_amount" not in data:
            data["vat_amount"] = data.pop("vat")
        
        return data


    def extract_invoice_data(
        self,
        file_content: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract invoice data using 100% AI (OpenAI Vision API):
        1. Convert PDFs to images if needed (PyMuPDF)
        2. Send images directly to OpenAI Vision API for analysis
        
        Args:
            file_content: File content as bytes
            filename: Name of the file
            content_type: MIME type of the file
            
        Returns:
            Tuple of (extracted_data, usage_info) where usage_info contains token counts
        """
        # Determine file type
        file_type = self._get_file_type(filename, content_type)
        
        # Step 1: Prepare content for OpenAI Vision API (100% AI, no OCR)
        system_prompt = """You are an expert invoice parser. Extract data from the invoice image with 100% accuracy.

CRITICAL RULES - FOLLOW EXACTLY:

1. DOCUMENT TYPE:
   - If you see "Fourni par" or "Provided by" → document_type = "invoice" (NEVER "gas_station_ticket")
   - If you see "TICKET CLIENT" → document_type = "receipt"
   - If you see fuel-related content WITHOUT "Fourni par" → document_type = "gas_station_ticket"

2. CUSTOMER NAME:
   - Find "Facturé à" or "Billed to" in the image
   - customer_name = FIRST line of text after this label
   - IGNORE all lines after (address, city, country)
   - Example: If you see "Facturé à\nOumar\n12 rue...\nFrance" → customer_name = "Oumar" (NOT "France")

3. SHOP DETAILS (from "Fourni par" section):
   - shop_name = First line after "Fourni par" (e.g., "Electra SAS")
   - shop_address = ALL address lines combined (e.g., "104 Rue de Richelieu, 75002 Paris")
   - shop_phone = Phone number from this section
   - vat_number = Number starting with "FR" + 11 chars (e.g., "FR45891624884") - NOT labels like "COMMUNAUTAIREFR4"

4. ITEMS:
   - Find the table with products/services
   - Extract EVERY row that has a product name (like "Énergie")
   - Each item needs: description, quantity, unit_price_ht, total_ht, vat_rate
   - If you see "Énergie" in the table, extract it as an item

5. TOTALS:
   - total_ht = "Prix total HT" or "TOTAL HT"
   - total_ttc = "Prix total TTC" or "TOTAL TTC"
   - vat_amount = "TVA" amount in currency (NOT percentage)

EXAMPLE OF CORRECT EXTRACTION:
If you see in the image:
  "Fourni par
   Electra SAS
   104 Rue de Richelieu
   75002 Paris
   FR45891624884
   01 86 65 99 99"
  
  "Facturé à
   Oumar
   12 rue du 19 mars 1962.
   93440 Dugny
   France"
  
  Items table:
  "Énergie | 20% | 43,101 kWh | 10,42 € | 12,50 €"
  
  Totals:
  "Prix total HT: 10,42 €
   TVA 20%: 2,08 €
   Prix total TTC: 12,50 €"

CORRECT OUTPUT:
{
  "document_type": "invoice",  // NOT "gas_station_ticket" because "Fourni par" is present
  "shop_name": "Electra SAS",
  "shop_address": "104 Rue de Richelieu, 75002 Paris",
  "shop_phone": "01 86 65 99 99",
  "customer_name": "Oumar",  // NOT "France" - France is the country, Oumar is the name
  "vat_number": "FR45891624884",  // NOT "COMMUNAUTAIREFR4" - extract the actual number
  "items": [
    {
      "description": "Énergie",  // MUST extract this - it's in the table
      "quantity": 43.101,
      "unit_price_ht": 10.42,
      "total_ht": 10.42,
      "vat_rate": 20
    }
  ],
  "total_ht": 10.42,
  "total_ttc": 12.50,
  "vat_amount": 2.08
}

FOLLOW THESE STRICT RULES:

VISUAL ANCHORS - USE THESE EXACT PATTERNS:

1. CUSTOMER NAME (CRITICAL):
   - Find the line that says "Facturé à" or "Billed to" or "Facture à"
   - The customer name is ALWAYS the FIRST line immediately after this label
   - Extract ONLY the first line (the name), ignore all subsequent lines (address, city, country)
   - Example: If you see:
     "Facturé à
     Oumar
     12 rue du 19 mars 1962.
     93440 Dugny
     France"
   - Extract customer_name = "Oumar" (NOT "France", NOT the address)
   - NEVER use country names (France, Belgium, etc.) as customer_name
   - NEVER use address lines as customer_name

2. SHOP DETAILS (Fourni par / Provided by):
   - Find the section labeled "Fourni par" or "Provided by" or "Fournisseur"
   - Extract from this section ONLY:
     - shop_name: The company name (first line after "Fourni par", e.g., "Electra SAS")
     - shop_address: ALL address lines (street, city, postal code, country) - combine into one string
     - shop_phone: Phone number (format: XX XX XX XX XX or +33X...)
     - shop_email: Email address (contains @)
     - vat_number: VAT number starting with country code (e.g., FR45891624884) - look for "TVA intracommunautaire" or pattern FR + 11 chars
     - siret: SIRET (14 digits) or SIREN (9 digits) if present
     - iban: IBAN if present (FR: 27 chars, others: 15-34 chars)

CRITICAL RULES - READ CAREFULLY:
1. Do NOT invent placeholder/example values. If a field cannot be found, use null (or 0 for totals if explicitly shown as 0).
2. The invoice may be in French and amounts may use comma decimals (e.g. 5200,00€). Convert to numbers with dot decimals.
3. For dates, always return YYYY-MM-DD format.

DOCUMENT TYPE DETECTION (CRITICAL - analyze the ENTIRE document structure):
RULE: If you see "Fourni par" or "Provided by" in the document, it is ALWAYS "invoice", NEVER "gas_station_ticket" or "receipt".

- "invoice" (facture): Has "FACTURE", "INVOICE", "Facture n°", "Invoice N°", "Date de facturation", "Date d'échéance", "Prix HT", "Prix TTC", "TVA", "Fourni par", "Facturé à", structured layout with seller/buyer sections, items table, totals section. 
  **IF "Fourni par" IS PRESENT, document_type MUST BE "invoice"**
- "receipt" (ticket de caisse): Has "TICKET CLIENT", "TICKET DE CAISSE", "RECU", "RECEIPT", "ARTICLE", "MERCI", "A bientôt", "THANK YOU", usually short format, often from retail stores, NO "Fourni par" section
- "gas_station_ticket" (ticket essence): Has "STATION", "ESSENCE", "CARBURANT", "GAZOLE", "DIESEL", "SP95", "SP98", "E10", "LITRE", "LITRES", "L", "KM", "KILOMETRAGE", "PUMP", "POMPE", "BUSE", "STATION ID", fuel-related content, NO "Fourni par" or "Facturé à" sections
  **IF "Fourni par" IS PRESENT, IT CANNOT BE "gas_station_ticket"**
- "parking_ticket": Has "PARKING", "PARK", "HORODATEUR", "HORODATAGE", "ENTREE", "SORTIE", "ENTRÉE", "DURÉE", "DUREE", parking-related content
- "estimate" (devis): Has "DEVIS", "QUOTE", "ESTIMATE", "ESTIMATION", "PROFORMA", usually has "Valable jusqu'au" or similar validity date
- "unknown": If none of the above match clearly

SELLER BLOCK (Fourni par / Provided by) - Extract from this section:
- shop_name: Company name (e.g., "Electra SAS") - NOT the label "Fourni par"
- shop_address: Full address (street, city, postal code, country) - ALL lines of the address
- shop_phone: Phone number (format: XX XX XX XX XX or +33X...)
- shop_email: Email address (contains @)
- siret: SIRET (14 digits) or SIREN (9 digits) - look for "SIRET" or "SIREN" label
- vat_number: VAT intracommunity number - look for "TVA intracommunautaire", "VAT intracommunity", or pattern like FR + 11 digits/alphanumeric
  - Format: Country code (2 letters) + digits/alphanumeric
  - French: FR + 11 characters (e.g., FR45891624884)
  - Return WITHOUT spaces
  - CRITICAL: Extract the ACTUAL number (e.g., "FR45891624884"), NOT labels like "COMMUNAUTAIREFR4" or "TVA intracommunautaire"
  - Look for patterns like "FR" followed by 11 digits or alphanumeric characters
- iban: IBAN - look for "IBAN" or "RIB" label, or pattern like FR + 2 digits + 23 alphanumeric
  - French IBAN: exactly 27 characters (FR + 2 digits + 23 alphanumeric)
  - Example: FR1420041010050500013M02606
  - Return WITHOUT spaces

BUYER BLOCK (Facturé à / Billed to) - Extract from this section:
- customer_name: Person or company name - NOT the label "Facturé à", NOT country names like "France", "Belgium"
  - If you see "France" as a country in the address, it's NOT the customer name
  - The customer name is usually the FIRST line after "Facturé à" or "Billed to"
  - Example: "Oumar" (not "France")

3. ITEM EXTRACTION (CRITICAL - THIS IS MANDATORY):
   - You MUST return a list of objects for 'items' (even if empty, return empty array [])
   - Find the items TABLE with columns: "Description", "Désignation", "TVA", "Quantité", "Qty", "Prix HT", "Prix TTC", "Montant", "Total"
   - For EACH data row in the table (NOT header row, NOT total rows):
     - Extract these 5 fields EXACTLY:
       1. description: Product/service name (REQUIRED - e.g., "Énergie")
       2. quantity: Quantity as number (extract number from "43,101 kWh" → 43.101)
       3. unit_price_ht: Unit price excluding VAT (from "Prix HT" column, e.g., 10.42)
       4. total_ht: Total price excluding VAT (if separate column, otherwise calculate: quantity × unit_price_ht)
       5. vat_rate: VAT rate as percentage (e.g., 20 for "20%", or null if not found)
     - Example row: "Énergie" | "20%" | "43,101 kWh" | "10,42 €" | "12,50 €"
       → Extract as: {
           "description": "Énergie",
           "quantity": 43.101,
           "unit_price_ht": 10.42,
           "total_ht": 10.42,
           "vat_rate": 20
         }
   - CRITICAL RULES:
     * You MUST extract at least ONE item if there is any product/service listed in a table
     * If you see "Énergie" or any product name in a table row, that IS an item - extract it
     * Do NOT skip items - extract ALL data rows from the table
     * Do NOT include header rows (rows with only "Description", "Quantité", etc.)
     * Do NOT include total rows (rows with "TOTAL HT", "TOTAL TTC", "SOUS-TOTAL", "NET A PAYER")
     * If quantity has a unit (e.g., "43,101 kWh"), extract ONLY the number part (43.101)
     * Convert comma decimals to dot decimals (10,42 → 10.42)
     * If the items array is empty but you see a product/service in the image, you made an error - extract it

4. TOTALS VALIDATION (CRITICAL):
   - Extract from summary section:
     - total_ht: Look for "Prix total HT", "TOTAL HT", "Total HT", "Hors taxe" (number, 0 if not found)
     - total_ttc: Look for "Prix total TTC", "TOTAL TTC", "Total TTC", "TTC" (number, 0 if not found)
     - vat_amount: Look for "TVA 20%" followed by amount, or "TVA" followed by amount (NOT percentage), extract the AMOUNT (number, 0 if not found)
   - VALIDATION RULE: Check that (total_ht + vat_amount) = total_ttc (within 0.01 tolerance for rounding)
   - If validation fails, set validation_error = true and include error message
   - If validation passes, set validation_error = false

STRICT OUTPUT SCHEMA - Return ONLY this exact JSON structure:
{
  "document_type": "invoice" | "receipt" | "gas_station_ticket" | "parking_ticket" | "estimate" | "unknown",
  "shop_name": "string" | null,
  "shop_address": "string" | null,
  "shop_phone": "string" | null,
  "customer_name": "string" | null,
  "date": "YYYY-MM-DD" | null,
  "invoice_number": "string" | null,
  "total_ht": number | 0,
  "total_ttc": number | 0,
  "vat_amount": number | 0,
  "validation_error": boolean,
  "validation_message": "string" | null,
  "items": [
    {
      "description": "string",
      "quantity": number | null,
      "unit_price_ht": number | null,
      "total_ht": number | null,
      "vat_rate": number | null
    }
  ],
  "vat_number": "string" | null,
  "siret": "string" | null,
  "iban": "string" | null
}

FIELD REQUIREMENTS:
- document_type: "invoice" if "Fourni par" present, "receipt" if "TICKET CLIENT", "gas_station_ticket" if fuel-related, etc.
- shop_name: From "Fourni par" section, first line (company name)
- shop_address: From "Fourni par" section, ALL address lines combined
- shop_phone: From "Fourni par" section
- customer_name: FIRST line after "Facturé à" (NOT address, NOT country)
- date: YYYY-MM-DD format
- invoice_number: From header (look for "Facture n°", "Invoice N°")
- total_ht: Number (0 if not found)
- total_ttc: Number (0 if not found)
- vat_amount: VAT amount in currency (NOT percentage, 0 if not found)
- validation_error: true if (total_ht + vat_amount) ≠ total_ttc, false otherwise
- validation_message: Error description if validation_error is true, null otherwise
- items: Array of item objects (MUST be array, even if empty [])
  - Each item MUST have: description, quantity, unit_price_ht, total_ht, vat_rate
- vat_number: VAT intracommunity number (e.g., FR45891624884) from "Fourni par" section
- siret: SIRET (14 digits) or SIREN (9 digits) if present
- iban: IBAN if present (FR: 27 chars, others: 15-34 chars)

CRITICAL: Follow visual anchors exactly. Customer name is FIRST line after "Facturé à", NOT subsequent lines."""

        user_prompt = """Analyze this invoice/receipt image CAREFULLY and extract all fields using STRICT VISUAL ANCHORS.

FOLLOW THESE STEPS EXACTLY - READ THE IMAGE, DON'T GUESS:

STEP 1: DOCUMENT TYPE
   - Look for "Fourni par" or "Provided by" in the image
   - If you see "Fourni par", document_type MUST be "invoice" (NOT "gas_station_ticket")
   - If you see "Fourni par" + "Facturé à", it's definitely an "invoice"

STEP 2: Find "Facturé à" or "Billed to"
   - Look at the image and find the section labeled "Facturé à"
   - customer_name = FIRST line of text immediately after "Facturé à"
   - IGNORE all subsequent lines (address, city, country)
   - If the first line is "Oumar", extract "Oumar" (NOT "France" which is on a later line)
   - NEVER extract country names like "France", "Belgium" as customer_name

STEP 3: Find "Fourni par" or "Provided by"
   - Look at the image and find the section labeled "Fourni par"
   - shop_name = First line of text after "Fourni par" (e.g., "Electra SAS")
   - shop_address = ALL address lines after shop_name (combine into one string: "104 Rue de Richelieu, 75002 Paris")
   - shop_phone = Phone number from this section (format: XX XX XX XX XX)
   - vat_number = Look for a number starting with "FR" followed by 11 digits/alphanumeric (e.g., "FR45891624884")
     * Extract the ACTUAL number, NOT labels like "COMMUNAUTAIREFR4" or "TVA intracommunautaire"
     * Look for patterns like "FR" + 11 characters

STEP 4: Find the ITEMS TABLE
   - Look at the image and find the table with columns like "Description", "Quantité", "Prix HT", "Prix TTC"
   - Extract EVERY row that contains a product/service name (like "Énergie")
   - For each row, extract: description, quantity, unit_price_ht, total_ht, vat_rate
   - If you see "Énergie" in a table row, that IS an item - you MUST extract it
   - You MUST return an array of items (if you see products in the table, extract them)
   - If items array is empty but you see a product in the image, you made an error

STEP 5: Find TOTALS section
   - total_ht = Look for "Prix total HT" or "TOTAL HT" and extract the number
   - total_ttc = Look for "Prix total TTC" or "TOTAL TTC" and extract the number
   - vat_amount = Look for "TVA" followed by an amount in currency (NOT percentage, the actual amount like "2,08 €")
   - Validate: (total_ht + vat_amount) should equal total_ttc

CRITICAL - READ THE IMAGE CAREFULLY:
- Look at the actual text in the image, don't guess
- customer_name is the PERSON/COMPANY name (first line after "Facturé à"), NOT the country
- items MUST be extracted from the table - if you see "Énergie" in a table, extract it
- vat_number is the actual number (FR45891624884), NOT labels or partial text
- document_type is "invoice" if "Fourni par" is present, NOT "gas_station_ticket"

Return ONLY the JSON object, no extra text or explanations."""

        try:
            # Log what we're sending (for debugging)
            print(f"\n[AI] Using model: {self.model}")
            print(f"[AI] File type: {file_type}")
            print(f"[AI] System prompt length: {len(system_prompt)} chars")
            print(f"[AI] User prompt length: {len(user_prompt)} chars")
            
            if file_type == "image":
                # Use Vision API for images (100% AI)
                file_base64 = base64.b64encode(file_content).decode("utf-8")
                mime = self._mime_from_filename(filename)
                print(f"[AI] Image size: {len(file_content)} bytes, base64: {len(file_base64)} chars")
                
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
                                        "url": f"data:{mime};base64,{file_base64}",
                                        "detail": "high",  # High detail for best accuracy
                                    }
                                }
                            ]
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,  # Deterministic for consistency
                )
                
                print(f"[AI] Response received: {response.usage.total_tokens} tokens")
            elif file_type == "pdf":
                # Render PDF pages to images and send as multi-image vision input
                pages_b64 = self._pdf_to_png_pages_base64(file_content, max_pages=3)
                content_parts: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
                for b64 in pages_b64:
                    content_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",  # High detail for best accuracy
                            },
                        }
                    )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content_parts},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,  # Deterministic for consistency
                )
            else:
                raise Exception(
                    f"Unsupported file type ({file_type}). Please upload an image (PNG/JPG) or a PDF."
                )
            
            # Parse response
            result = response.choices[0].message.content
            print(f"[AI] Raw response length: {len(result)} chars")
            print(f"[AI] Raw response preview: {result[:200]}...")
            
            extracted_data = json.loads(result)
            print(f"[AI] Parsed JSON successfully")
            print(f"[AI] document_type: {extracted_data.get('document_type')}")
            print(f"[AI] customer_name: {extracted_data.get('customer_name')}")
            print(f"[AI] items count: {len(extracted_data.get('items', []))}")
            
            # Validate required fields
            required_fields = ["document_type", "shop_name", "customer_name", "date", "total_ht", "total_ttc", "vat_amount", "items", "validation_error"]
            for field in required_fields:
                if field not in extracted_data:
                    if field in ["total_ht", "total_ttc", "vat_amount"]:
                        extracted_data[field] = 0
                    elif field == "items":
                        extracted_data[field] = []
                    elif field == "document_type":
                        extracted_data[field] = "unknown"
                    elif field == "validation_error":
                        extracted_data[field] = False
                    else:
                        extracted_data[field] = None
            
            # Ensure optional fields exist
            for field in ["invoice_number", "ticket_number", "iban", "siret", "vat_number", "shop_address", "shop_phone", "shop_email", "validation_message"]:
                if field not in extracted_data:
                    extracted_data[field] = None
            
            # Perform totals validation if not already done
            if extracted_data.get("validation_error") is None:
                total_ht = extracted_data.get("total_ht", 0) or 0
                vat_amount = extracted_data.get("vat_amount", 0) or 0
                total_ttc = extracted_data.get("total_ttc", 0) or 0
                expected_ttc = total_ht + vat_amount
                # Allow 0.01 tolerance for rounding
                if abs(expected_ttc - total_ttc) > 0.01:
                    extracted_data["validation_error"] = True
                    extracted_data["validation_message"] = f"Totals validation failed: {total_ht} + {vat_amount} = {expected_ttc}, but total_ttc = {total_ttc}"
                else:
                    extracted_data["validation_error"] = False
                    extracted_data["validation_message"] = None
            
            # Post-processing validation and cleanup
            extracted_data = self._validate_and_clean_extracted_data(extracted_data)
            
            # Extract usage information
            usage_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return extracted_data, usage_info
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response from OpenAI: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to extract invoice data: {str(e)}")

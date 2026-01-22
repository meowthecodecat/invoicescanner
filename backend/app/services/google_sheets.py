"""Google Sheets service with dynamic tab creation per run."""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


class GoogleSheetsService:
    """Service for interacting with Google Sheets API."""
    
    def __init__(self, refresh_token: str):
        """
        Initialize Google Sheets service with refresh token.
        
        Args:
            refresh_token: Google OAuth refresh token
        """
        self.refresh_token = refresh_token
        self._credentials: Optional[Credentials] = None
        self._service = None
    
    def _get_credentials(self) -> Credentials:
        """Get or refresh Google credentials."""
        if self._credentials is None or not self._credentials.valid:
            # Create credentials from refresh token
            self._credentials = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
            )
            
            # Refresh the token
            if not self._credentials.valid:
                self._credentials.refresh(Request())
        
        return self._credentials
    
    def _get_service(self):
        """Get Google Sheets API service."""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build('sheets', 'v4', credentials=credentials)
        
        return self._service
    
    def get_or_create_run_tab(self, spreadsheet_id: str) -> str:
        """
        Get or create a new tab for this run.
        Tab naming: "Run_YYYY-MM-DD_HHmm"
        
        Args:
            spreadsheet_id: Google Spreadsheet ID
            
        Returns:
            Tab name (worksheet title)
        """
        # Generate tab name based on current timestamp
        now = datetime.now()
        tab_name = f"Run_{now.strftime('%Y-%m-%d_%H%M')}"
        
        service = self._get_service()
        
        try:
            # Get all worksheets
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            worksheets = spreadsheet.get('sheets', [])
            
            # Check if tab already exists
            for sheet in worksheets:
                if sheet['properties']['title'] == tab_name:
                    # Tab exists, return it
                    return tab_name
            
            # Tab doesn't exist, create it
            requests = [{
                'addSheet': {
                    'properties': {
                        'title': tab_name,
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': 20
                        }
                    }
                }
            }]
            
            body = {'requests': requests}
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            
            # Add header row with all extracted fields
            headers = [
                "Document Type", "Shop Name", "Shop Address", "Shop Phone", "Shop Email",
                "Customer Name", "Date", "Invoice Number", "Ticket Number",
                "Total HT", "Total TTC", "VAT Amount", "Validation Error", "Validation Message",
                "IBAN", "SIRET", "VAT Number", "Items"
            ]
            self._append_row(spreadsheet_id, tab_name, headers)
            
            return tab_name
            
        except Exception as e:
            raise Exception(f"Failed to get or create tab: {str(e)}")
    
    def _append_row(self, spreadsheet_id: str, tab_name: str, row_data: list):
        """
        Append a row to the specified tab.
        
        Args:
            spreadsheet_id: Google Spreadsheet ID
            tab_name: Name of the tab/worksheet
            row_data: List of values to append
        """
        service = self._get_service()
        
        range_name = f"{tab_name}!A:R"
        body = {
            "values": [row_data]
        }
        
        try:
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
        except Exception as e:
            raise Exception(f"Failed to append row to sheet: {str(e)}")
    
    def _format_items(self, items: list) -> str:
        """
        Format items list into a human-readable string.
        
        Args:
            items: List of item dicts with description, quantity, unit_price_ht, total_ht, vat_rate
            
        Returns:
            Formatted string like "Item 1 (qty x price = total), Item 2 (...)"
        """
        if not items:
            return ""
        
        formatted_items = []
        for item in items:
            desc = item.get("description", "")
            qty = item.get("quantity") or 0
            # Support both old and new field names
            unit_price = item.get("unit_price_ht") or item.get("unit_price") or 0
            total = item.get("total_ht") or item.get("total") or 0
            vat_rate = item.get("vat_rate")
            
            # Format: "Description (qty x unit_price€ = total€ [VAT rate%])"
            if vat_rate:
                formatted_items.append(f"{desc} ({qty} x {unit_price:.2f}€ = {total:.2f}€ [TVA {vat_rate}%])")
            else:
                formatted_items.append(f"{desc} ({qty} x {unit_price:.2f}€ = {total:.2f}€)")
        
        # Join with newlines for better readability in Google Sheets
        return "\n".join(formatted_items)
    
    def write_invoice_data(self, spreadsheet_id: str, invoice_data: Dict[str, Any]) -> str:
        """
        Write invoice data to a new run tab.
        
        Args:
            spreadsheet_id: Google Spreadsheet ID
            invoice_data: Extracted invoice data dict
            
        Returns:
            Tab name where data was written
        """
        # Get or create run tab
        tab_name = self.get_or_create_run_tab(spreadsheet_id)
        
        # Format items as human-readable text
        items_formatted = self._format_items(invoice_data.get("items", []))
        
        # Build row with all extracted fields
        row_data = [
            invoice_data.get("document_type", ""),
            invoice_data.get("shop_name", ""),
            invoice_data.get("shop_address", ""),
            invoice_data.get("shop_phone", ""),
            invoice_data.get("shop_email", ""),
            invoice_data.get("customer_name", ""),
            invoice_data.get("date", ""),
            invoice_data.get("invoice_number", ""),
            invoice_data.get("ticket_number", ""),
            invoice_data.get("total_ht", ""),
            invoice_data.get("total_ttc", ""),
            invoice_data.get("vat_amount", invoice_data.get("vat", "")),  # Support both field names
            invoice_data.get("validation_error", False),
            invoice_data.get("validation_message", ""),
            invoice_data.get("iban", ""),
            invoice_data.get("siret", ""),
            invoice_data.get("vat_number", ""),
            items_formatted
        ]
        
        # Append row
        self._append_row(spreadsheet_id, tab_name, row_data)
        
        return tab_name
    
    # Future: Easy switch to monthly tabs
    # Uncomment and modify this method when switching to monthly tabs
    # def get_or_create_monthly_tab(self, spreadsheet_id: str, invoice_date: str) -> str:
    #     """
    #     Get or create a monthly tab based on invoice date.
    #     Tab naming: "Factures_MM_YYYY"
    #     
    #     Args:
    #         spreadsheet_id: Google Spreadsheet ID
    #         invoice_date: Invoice date in YYYY-MM-DD format
    #         
    #     Returns:
    #         Tab name (worksheet title)
    #     """
    #     # Parse date and create tab name
    #     date_obj = datetime.strptime(invoice_date, "%Y-%m-%d")
    #     tab_name = f"Factures_{date_obj.strftime('%m_%Y')}"
    #     
    #     # Similar logic to get_or_create_run_tab but with monthly naming
    #     # ... (implementation similar to get_or_create_run_tab)
    #     
    #     return tab_name

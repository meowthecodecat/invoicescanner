"""Test script to debug OpenAI invoice extraction."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
backend_dir = Path(__file__).parent
env_path = backend_dir.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Add backend to path
sys.path.insert(0, str(backend_dir))

from app.services.ai import AIService

def test_extraction(image_path: str):
    """Test invoice extraction with detailed logging."""
    print("=" * 80)
    print("TESTING OPENAI INVOICE EXTRACTION")
    print("=" * 80)
    
    # Check model
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    print(f"\n📋 Model: {model}")
    print(f"📋 API Key: {'SET' if os.getenv('OPENAI_API_KEY') else 'MISSING'}")
    
    # Initialize service
    try:
        service = AIService()
        print(f"✅ Service initialized with model: {service.model}")
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return
    
    # Read image
    image_file = Path(image_path)
    if not image_file.exists():
        print(f"❌ Image not found: {image_path}")
        return
    
    print(f"\n📷 Reading image: {image_path}")
    with open(image_file, 'rb') as f:
        image_bytes = f.read()
    
    print(f"📷 Image size: {len(image_bytes)} bytes")
    
    # Extract data
    print("\n🔄 Calling OpenAI Vision API...")
    try:
        extracted_data, usage_info = service.extract_invoice_data(
            image_bytes,
            image_file.name,
            "image/jpeg" if image_file.suffix.lower() in ['.jpg', '.jpeg'] else "image/png"
        )
        
        print("\n" + "=" * 80)
        print("RESULTS:")
        print("=" * 80)
        print(f"\n📊 Document Type: {extracted_data.get('document_type')}")
        print(f"🏪 Shop Name: {extracted_data.get('shop_name')}")
        print(f"📍 Shop Address: {extracted_data.get('shop_address')}")
        print(f"📞 Shop Phone: {extracted_data.get('shop_phone')}")
        print(f"👤 Customer Name: {extracted_data.get('customer_name')}")
        print(f"📅 Date: {extracted_data.get('date')}")
        print(f"🔢 Invoice Number: {extracted_data.get('invoice_number')}")
        print(f"💰 Total HT: {extracted_data.get('total_ht')}")
        print(f"💰 Total TTC: {extracted_data.get('total_ttc')}")
        print(f"💰 VAT Amount: {extracted_data.get('vat_amount')}")
        print(f"🔍 VAT Number: {extracted_data.get('vat_number')}")
        print(f"🔍 SIRET: {extracted_data.get('siret')}")
        print(f"🔍 IBAN: {extracted_data.get('iban')}")
        print(f"✅ Validation Error: {extracted_data.get('validation_error')}")
        print(f"📝 Validation Message: {extracted_data.get('validation_message')}")
        
        items = extracted_data.get('items', [])
        print(f"\n📦 Items ({len(items)}):")
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item.get('description')} - Qty: {item.get('quantity')} - Price HT: {item.get('unit_price_ht')} - Total HT: {item.get('total_ht')} - VAT: {item.get('vat_rate')}%")
        
        print(f"\n💵 Usage: {usage_info.get('total_tokens')} tokens ({usage_info.get('prompt_tokens')} prompt + {usage_info.get('completion_tokens')} completion)")
        
        # Check for common errors
        print("\n" + "=" * 80)
        print("ERROR CHECK:")
        print("=" * 80)
        errors = []
        if extracted_data.get('document_type') == 'gas_station_ticket' and extracted_data.get('shop_name'):
            errors.append("❌ document_type is 'gas_station_ticket' but shop_name exists (should be 'invoice')")
        if extracted_data.get('customer_name') == 'France':
            errors.append("❌ customer_name is 'France' (should be person name like 'Oumar')")
        if not extracted_data.get('shop_address'):
            errors.append("⚠️ shop_address is empty")
        if not items:
            errors.append("⚠️ items array is empty (should contain at least 'Énergie')")
        if extracted_data.get('vat_number') and 'COMMUNAUTAIRE' in extracted_data.get('vat_number', ''):
            errors.append(f"❌ vat_number is '{extracted_data.get('vat_number')}' (should be like 'FR45891624884')")
        
        if errors:
            for error in errors:
                print(error)
        else:
            print("✅ No obvious errors detected")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_extraction(sys.argv[1])
    else:
        print("Usage: python test_ai_extraction.py <path_to_invoice_image>")
        print("\nExample:")
        print("  python test_ai_extraction.py ../test_invoice.jpg")

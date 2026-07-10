"""
Information Extraction Engine (LLM-Powered)
Uses Groq API to extract structured JSON from raw text.
Replaces legacy regex heuristics.
"""
import json
from typing import Any, List
from engine.clean import clean_ocr_text
from app.config import settings

try:
    import groq
except ImportError:
    groq = None

SYSTEM_PROMPT = """You are an expert OCR invoice parser, serving as a Chartered Accountant's extraction tool.
Extract all relevant financial and accounting fields from the invoice text.
Return ONLY a valid JSON object matching this exact schema:
{
  "fields": {
    "invoice_number": "string or null",
    "invoice_date": "YYYY-MM-DD or null",
    "due_date": "YYYY-MM-DD or null",
    "vendor_name": "string or null",
    "vendor_address": "string or null",
    "vendor_tax_id": "string or null (e.g. GSTIN, VAT, EIN, PAN)",
    "vendor_phone": "string or null",
    "vendor_email": "string or null",
    "buyer_name": "string or null",
    "buyer_address": "string or null",
    "buyer_tax_id": "string or null",
    "subtotal": float or null,
    "tax_amount": float or null,
    "total_amount": float or null,
    "discount_amount": float or null,
    "shipping_charges": float or null,
    "currency": "3-letter ISO code like USD, INR, EUR or null",
    "payment_terms": "string or null",
    "po_number": "string or null",
    "bank_name": "string or null",
    "bank_account_number": "string or null",
    "bank_routing_number": "string or null (e.g. IFSC, SWIFT, Routing)",
    "tax_breakdown": [
      {
        "tax_name": "string (e.g. CGST, SGST, IGST, State Tax)",
        "tax_rate": float or null (e.g. 9.0),
        "tax_amount": float or null
      }
    ]
  },
  "line_items": [
    {
      "description": "string",
      "hsn_code": "string or null (e.g. HSN/SAC code)",
      "quantity": float or null,
      "unit": "string or null",
      "unit_price": float or null,
      "amount": float or null,
      "tax_rate": float or null,
      "discount": float or null
    }
  ]
}

Extraction Rules:
1. Dates MUST be formatted exactly as YYYY-MM-DD.
2. Amounts and rates MUST be raw floats (e.g. 1234.56). NO commas or currency symbols.
3. Use `null` for missing fields. Do NOT guess or hallucinate.
4. "tax_breakdown" must be a list. If there is no tax breakdown, return an empty list `[]` or null.
5. Provide the output in strict JSON format with NO markdown blocks or surrounding text.
"""

async def extract_fields(tokens: List[Any], raw_text: str) -> dict:
    """
    Main extraction function using Groq API and LLM JSON parsing.
    """
    if not groq:
        raise ImportError("The 'groq' library is not installed. Run 'pip install groq'.")
        
    api_key = settings.groq_api_key
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set. Cannot perform LLM extraction.")

    text = clean_ocr_text(raw_text)
    
    if not text.strip():
        # Empty document
        return {
            "fields": {},
            "confidence_scores": {},
            "line_items": [],
            "needs_review": True,
        }

    user_prompt = f"Extract the invoice data from the following parsed text:\n\n{text}"

    client = groq.AsyncGroq(api_key=api_key)
    
    response = await client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,  # Low temperature for deterministic extraction
        max_tokens=1500,
    )

    result_content = response.choices[0].message.content
    try:
        parsed_data = json.loads(result_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {result_content}")

    fields = parsed_data.get("fields", {})
    line_items = parsed_data.get("line_items", [])
    
    confidence = {}
    for k, v in fields.items():
        # Set a baseline high confidence if the LLM found the field
        confidence[k] = 0.95 if v is not None else 0.0

    return {
        "fields": fields,
        "confidence_scores": confidence,
        "line_items": line_items,
        "needs_review": False,
    }

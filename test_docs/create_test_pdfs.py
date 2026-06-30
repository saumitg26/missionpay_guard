"""Create synthetic test PDFs for MissionPay Guard demo.

These match the SF 1034 (Invoice), SF 1449 (PO), and Contract Award Reference
documents that will be uploaded through the pipeline.
"""
import os

# We'll use reportlab if available, otherwise create minimal PDFs manually
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def create_pdf_simple(filename, lines):
    """Create a minimal valid PDF with text content."""
    # Minimal PDF structure
    text_content = "\n".join(lines)
    
    # Build a minimal PDF manually
    objects = []
    
    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    
    # Object 2: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    
    # Object 4: Font
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n")
    
    # Object 5: Stream content
    # Build text drawing commands
    text_ops = []
    text_ops.append("BT")
    text_ops.append("/F1 9 Tf")
    y = 750
    for line in lines:
        # Escape special PDF characters
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        text_ops.append(f"1 0 0 1 50 {y} Tm")
        text_ops.append(f"({safe_line}) Tj")
        y -= 12
        if y < 50:
            break
    text_ops.append("ET")
    stream_content = "\n".join(text_ops).encode()
    
    stream_obj = f"5 0 obj\n<< /Length {len(stream_content)} >>\nstream\n".encode()
    stream_obj += stream_content
    stream_obj += b"\nendstream\nendobj\n"
    objects.append(stream_obj)
    
    # Object 3: Page
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>\nendobj\n")
    
    # Build PDF
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    
    # Cross-reference table
    xref_offset = len(pdf)
    pdf += b"xref\n"
    pdf += f"0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    
    # Map object numbers to offsets
    obj_map = {1: offsets[0], 2: offsets[1], 4: offsets[2], 5: offsets[3], 3: offsets[4]}
    for i in range(1, len(objects) + 1):
        if i in obj_map:
            pdf += f"{obj_map[i]:010d} 00000 n \n".encode()
    
    pdf += b"trailer\n"
    pdf += f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    pdf += b"startxref\n"
    pdf += f"{xref_offset}\n".encode()
    pdf += b"%%EOF\n"
    
    with open(filename, "wb") as f:
        f.write(pdf)
    
    print(f"Created: {filename} ({len(pdf)} bytes)")


# Invoice - SF 1034
invoice_lines = [
    "SYNTHETIC TEST DOCUMENT - NOT REAL - FOR HACKATHON DEMO ONLY",
    "PUBLIC VOUCHER FOR PURCHASES AND SERVICES OTHER THAN PERSONAL",
    "SF 1034-style invoice / payment voucher",
    "",
    "STANDARD FORM: SF 1034",
    "VOUCHER NO.: INV-8821",
    "CASE ID: MPG-SYN-0001",
    "DEPARTMENT: Department of Community Resilience",
    "PROGRAM: Emergency Medical Supply Replenishment Program",
    "DATE VOUCHER PREPARED: 06/30/2026",
    "PAYMENT OFFICE: Department of Community Resilience Finance Office, Washington, DC 20410",
    "",
    "PAYEE NAME AND ADDRESS:",
    "Acme Medical Supply LLC",
    "2450 Liberty Industrial Parkway, Arlington, VA 22202",
    "UEI: ACME12345SYN",
    "",
    "CONTRACT NUMBER AND DATE: CON-2025-1? / 06/20/2026",
    "  (intentionally unclear final digit for OCR review)",
    "REQUISITION NUMBER AND DATE: REQ-7742 / 06/18/2026",
    "ORDER NUMBER AND DATE: PO-44519 / 06/20/2026",
    "DATE OF DELIVERY OR SERVICE: 06/29/2026",
    "PAYMENT METHOD / TERMS: ACH / Net 30",
    "",
    "ARTICLES OR SERVICES:",
    "Item  Description                              Qty  Unit  Price     Amount",
    "001   Portable emergency medical response kits 200  EA    $350.00   $70,000.00",
    "002   Replacement trauma supply modules        40   EA    $210.00   $8,400.00",
    "003   Expedited handling and mission staging   1    LOT   $4,000.00 $4,000.00",
    "",
    "TOTAL AMOUNT: $82,400.00",
    "PAYMENT TYPE: Final [X] Complete [ ] Partial [ ]",
    "APPROVED FOR: $82,400.00",
    "CERTIFYING OFFICER: Maya Thompson",
    "ACCOUNTING CLASSIFICATION: DCR-EMR-2025-7742",
    "",
    "RISK TRIGGER: Contract field intentionally unclear and payment amount exceeds $50,000.",
]

# Purchase Order - SF 1449
po_lines = [
    "SYNTHETIC TEST DOCUMENT - NOT REAL - FOR HACKATHON DEMO ONLY",
    "SOLICITATION / CONTRACT / ORDER FOR COMMERCIAL PRODUCTS AND COMMERCIAL SERVICES",
    "SF 1449-style purchase order / order document",
    "",
    "1. REQUISITION NUMBER: REQ-7742",
    "2. CONTRACT NUMBER: CON-2025-19",
    "3. AWARD / EFFECTIVE DATE: 06/20/2026",
    "4. ORDER NUMBER: PO-44519",
    "CASE ID: MPG-SYN-0001",
    "",
    "9. ISSUED BY:",
    "Department of Community Resilience",
    "Office of Emergency Logistics",
    "1200 Preparedness Avenue, Washington, DC 20410",
    "",
    "15. DELIVER TO:",
    "National Response Logistics Annex",
    "4200 Readiness Drive, Fredericksburg, VA 22401",
    "",
    "17A. CONTRACTOR / OFFEROR:",
    "Acme Medical Supply LLC",
    "2450 Liberty Industrial Parkway, Arlington, VA 22202",
    "UEI: ACME12345SYN",
    "",
    "SCHEDULE OF SUPPLIES / SERVICES:",
    "Item  Description                              Qty  Unit  Price     Amount",
    "001   Portable emergency medical response kits 200  EA    $350.00   $70,000.00",
    "002   Replacement trauma supply modules        40   EA    $210.00   $8,400.00",
    "003   Expedited handling and mission staging   1    LOT   $4,000.00 $4,000.00",
    "",
    "25. ACCOUNTING AND APPROPRIATION DATA: DCR-EMR-2025-7742",
    "26. TOTAL AWARD AMOUNT: $82,400.00",
    "",
    "30A-C. CONTRACTOR SIGNATURE: Jordan Ellis - 06/20/2026",
    "31A-C. CONTRACTING OFFICER: Daniel Reed - 06/20/2026",
]

# Contract Award Reference
contract_lines = [
    "SYNTHETIC TEST DOCUMENT - NOT REAL - FOR HACKATHON DEMO ONLY",
    "CONTRACT / AWARD REFERENCE ADDENDUM",
    "Synthetic award summary attachment",
    "",
    "CONTRACT / AWARD NUMBER: CON-2025-19",
    "RELATED ORDER NUMBER: PO-44519",
    "REQUISITION NUMBER: REQ-7742",
    "AWARD EFFECTIVE DATE: 01/01/2026",
    "CONTRACT PERIOD: 01/01/2026 to 12/31/2026",
    "",
    "AWARDING AGENCY: Department of Community Resilience",
    "CONTRACTOR / VENDOR: Acme Medical Supply LLC",
    "VENDOR UEI: ACME12345SYN",
    "",
    "CONTRACT CEILING: $500,000.00",
    "CURRENT ORDER AMOUNT: $82,400.00",
    "AUTHORIZED PRODUCT CATEGORY: Emergency medical logistics and response supply",
    "FUNDING LINE: DCR-EMR-2025-7742",
    "CONTRACTING OFFICER: Lena Ortiz",
    "PAYMENT OFFICE: Department of Community Resilience Finance Office",
    "",
    "SPECIAL PAYMENT CONTROL NOTE:",
    "Vendor banking information must match the approved vendor enrollment",
    "record before payment release. If banking information changed,",
    "finance and compliance review are required before simulated disbursement.",
    "",
    "EXPECTED VALIDATION RESULT:",
    "Contract exists, vendor matches, amount is within ceiling.",
    "Banking change still triggers review.",
]

os.makedirs("test_docs", exist_ok=True)

create_pdf_simple("test_docs/01-Invoice-SF1034-INV-8821.pdf", invoice_lines)
create_pdf_simple("test_docs/02-Purchase-Order-SF1449-PO-44519.pdf", po_lines)
create_pdf_simple("test_docs/03-Contract-Award-CON-2025-19.pdf", contract_lines)

print("\nAll 3 test PDFs created successfully!")

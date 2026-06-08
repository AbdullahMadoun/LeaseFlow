"""Generate a fake invoice PDF for the item the merchant wants financed."""
from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.documents import ExtractionMeta, InvoiceLine, InvoiceReport
from ._common import sar, seed_rng

VENDORS = [
    ("Arabian Espresso Co.",   "300123456700003"),
    ("Gulf Commercial Kitchen","310987654300003"),
    ("Al Wafaa Trading",       "302345678900003"),
    ("Saudi Hospitality Supply","304567891200003"),
]


def generate_invoice(
    *,
    seed: str,
    item_description: str,
    amount_sar: float,
    issue_date: date | None = None,
) -> tuple[bytes, InvoiceReport]:
    rng = seed_rng(seed, "invoice")
    vendor_name, vat = rng.choice(VENDORS)
    issue = issue_date or date.today() - timedelta(days=rng.randint(1, 20))
    invoice_number = f"INV-{issue.strftime('%Y%m')}-{rng.randint(1000, 9999)}"

    # Line items: usually 1 main item + optional install/delivery
    lines: list[InvoiceLine] = []
    main_price = amount_sar * rng.uniform(0.88, 0.96) / 1.15  # subtract VAT
    lines.append(InvoiceLine(
        description=item_description,
        quantity=1,
        unit_price_sar=round(main_price, 2),
        total_sar=round(main_price, 2),
    ))
    if rng.random() < 0.6:
        install = amount_sar * 0.03 / 1.15
        lines.append(InvoiceLine(
            description="Installation & commissioning",
            quantity=1,
            unit_price_sar=round(install, 2),
            total_sar=round(install, 2),
        ))
    if rng.random() < 0.4:
        delivery = amount_sar * 0.015 / 1.15
        lines.append(InvoiceLine(
            description="Delivery",
            quantity=1,
            unit_price_sar=round(delivery, 2),
            total_sar=round(delivery, 2),
        ))

    subtotal = sum(l.total_sar for l in lines)
    vat_amount = subtotal * 0.15
    total = subtotal + vat_amount

    report = InvoiceReport(
        vendor_name=vendor_name,
        vendor_vat=vat,
        invoice_number=invoice_number,
        issue_date=issue.isoformat(),
        line_items=lines,
        subtotal_sar=round(subtotal, 2),
        vat_sar=round(vat_amount, 2),
        total_sar=round(total, 2),
        item_category=_guess_category(item_description),
        matches_requested_amount=abs(total - amount_sar) / max(1, amount_sar) < 0.1,
        meta=ExtractionMeta(confidence=1.0, source_filename="invoice.pdf"),
    )

    pdf_bytes = _render(vendor_name, vat, invoice_number, issue, lines, subtotal, vat_amount, total)
    return pdf_bytes, report


def _guess_category(desc: str) -> str:
    d = desc.lower()
    if any(k in d for k in ("espresso", "coffee", "grinder", "brewer")):
        return "coffee_equipment"
    if any(k in d for k in ("oven", "range", "fryer", "griddle")):
        return "commercial_cooking"
    if any(k in d for k in ("fridge", "freezer", "chiller")):
        return "refrigeration"
    if any(k in d for k in ("pos", "terminal", "cashier")):
        return "pos_hardware"
    return "general_fnb_equipment"


def _render(vendor: str, vat: str, inv_no: str, issue: date,
            lines: list[InvoiceLine], subtotal: float,
            vat_amt: float, total: float) -> bytes:
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    flow: list[Any] = []

    flow.append(Paragraph(f"<b>{vendor}</b>", styles["Title"]))
    flow.append(Paragraph(f"VAT: {vat}", styles["Normal"]))
    flow.append(Spacer(1, 0.3 * cm))
    flow.append(Paragraph(
        f"<b>TAX INVOICE</b> &nbsp;&nbsp;|&nbsp;&nbsp; No: {inv_no} "
        f"&nbsp;&nbsp;|&nbsp;&nbsp; Date: {issue}",
        styles["Heading2"],
    ))
    flow.append(Spacer(1, 0.5 * cm))

    header = ["Description", "Qty", "Unit Price", "Total"]
    body = [[l.description, f"{l.quantity:g}", sar(l.unit_price_sar), sar(l.total_sar)] for l in lines]
    t = Table([header] + body, colWidths=[8 * cm, 2 * cm, 3 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 0.6 * cm))

    totals = [
        ["Subtotal", sar(subtotal)],
        ["VAT (15%)", sar(vat_amt)],
        ["TOTAL", sar(total)],
    ]
    t2 = Table(totals, colWidths=[11 * cm, 5 * cm])
    t2.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    flow.append(t2)
    flow.append(Spacer(1, 1 * cm))
    flow.append(Paragraph("Thank you for your business.", styles["Italic"]))

    doc.build(flow)
    return buf.getvalue()

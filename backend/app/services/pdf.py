"""Invoice and quote PDFs (plan v3, section 8: tax-invoice fields, ABN, "Tax Invoice").

A small PDF 1.4 writer using the standard Helvetica fonts, so no native dependencies are needed.
"""

from __future__ import annotations

import uuid
import zlib
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.engine.records import RecordService
from app.engine.types import display_text, money, to_decimal
from app.models import Record
from app.services.settings import get_setting

A4 = (595.28, 841.89)


def _esc(text: str) -> str:
    safe = text.encode("cp1252", "replace").decode("cp1252")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _width(text: str, size: float, bold: bool = False) -> float:
    # Average Helvetica glyph width is ~0.5em (bold ~0.55em); good enough for right alignment.
    return len(text) * size * (0.55 if bold else 0.5)


class PdfDoc:
    def __init__(self) -> None:
        self.pages: list[list[str]] = [[]]

    @property
    def ops(self) -> list[str]:
        return self.pages[-1]

    def new_page(self) -> None:
        self.pages.append([])

    def text(
        self,
        x: float,
        y: float,
        s: str,
        size: float = 10,
        bold: bool = False,
        align: str = "left",
        color: tuple[float, float, float] = (0.1, 0.12, 0.16),
    ) -> None:
        if align == "right":
            x -= _width(s, size, bold)
        r, g, b = color
        self.ops.append(
            f"BT {r:.3f} {g:.3f} {b:.3f} rg /{'F2' if bold else 'F1'} {size} Tf "
            f"{x:.2f} {y:.2f} Td ({_esc(s)}) Tj ET"
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float = 0.5, gray: float = 0.8) -> None:
        self.ops.append(f"{gray:.2f} G {width} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def rect(self, x: float, y: float, w: float, h: float, rgb: tuple[float, float, float]) -> None:
        self.ops.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def render(self) -> bytes:
        objects: list[bytes] = []

        def add(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        pages_id = len(objects) + 1 + 2 * len(self.pages)
        page_ids = []
        for ops in self.pages:
            stream = zlib.compress("\n".join(ops).encode("cp1252", "replace"))
            content = add(
                b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream"
            )
            page_ids.append(
                add(
                    (
                        f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {A4[0]} {A4[1]}] "
                        f"/Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >> "
                        f"/Contents {content} 0 R >>"
                    ).encode()
                )
            )
        kids = " ".join(f"{p} 0 R" for p in page_ids)
        add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
        catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        trailer = f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n"
        out += trailer.encode()
        return bytes(out)


def _money(v: Any) -> str:
    d = money(v)
    return f"${d:,.2f}"


def _fmt_date(v: Any) -> str:
    if not v:
        return ""
    try:
        return date.fromisoformat(str(v)[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(v)


def render_document(svc: RecordService, record: Record) -> bytes:
    """Tax invoice or quote. `record` must already be readable by `svc`."""
    is_invoice = record.object_api_name == "invoice"
    meta = svc.registry.get(record.object_api_name)
    company = get_setting(svc.db, "company") or {}
    branding = get_setting(svc.db, "branding") or {}
    billing = get_setting(svc.db, "billing") or {}
    line_obj = "invoice_line" if is_invoice else "quote_line"
    lines = list(
        svc.db.scalars(
            select(Record)
            .where(
                Record.object_api_name == line_obj,
                Record.is_deleted.is_(False),
                Record.data[record.object_api_name].astext == str(record.id),
            )
            .order_by(Record.created_at)
        )
    )
    lines.sort(key=lambda r: (to_decimal(r.data.get("sort_order")) or Decimal(0), r.created_at))
    account = (
        svc.db.get(Record, uuid.UUID(str(record.data["account"]))) if record.data.get("account") else None
    )
    contact = (
        svc.db.get(Record, uuid.UUID(str(record.data["contact"]))) if record.data.get("contact") else None
    )

    doc = PdfDoc()
    w, h = A4
    brand = branding.get("primary_color") or "#0176d3"
    rgb = tuple(int(brand[i : i + 2], 16) / 255 for i in (1, 3, 5)) if len(brand) == 7 else (0.0, 0.46, 0.83)
    doc.rect(0, h - 8, w, 8, rgb)  # type: ignore[arg-type]
    seller = company.get("legal_name") or branding.get("name") or "Your Company"
    doc.text(40, h - 60, seller, 16, bold=True)
    y = h - 76
    for part in (
        company.get("address"),
        f"ABN {company['abn']}" if company.get("abn") else None,
        company.get("email"),
        company.get("phone"),
    ):
        if part:
            doc.text(40, y, str(part), 9, color=(0.35, 0.38, 0.45))
            y -= 12
    if is_invoice:
        title = (
            "Tax Invoice"
            if billing.get("gst_registered", True) and record.data.get("status") != "Void"
            else "Invoice"
        )
        if record.data.get("status") == "Void":
            title = "VOID - Invoice"
        number = record.data.get("invoice_number") or "DRAFT"
    else:
        title = "Quote"
        number = record.name
    doc.text(w - 40, h - 60, title, 20, bold=True, align="right")
    doc.text(w - 40, h - 78, f"No. {number}", 10, align="right")
    info = []
    if is_invoice:
        info = [
            ("Issue date", _fmt_date(record.data.get("issue_date"))),
            ("Due date", _fmt_date(record.data.get("due_date"))),
            ("Status", str(record.data.get("status") or "")),
        ]
    else:
        info = [
            ("Date", _fmt_date(record.created_at.date().isoformat())),
            ("Valid until", _fmt_date(record.data.get("expiry_date"))),
            ("Status", str(record.data.get("status") or "")),
        ]
    yy = h - 96
    for label, value in info:
        doc.text(w - 140, yy, label, 9, color=(0.35, 0.38, 0.45))
        doc.text(w - 40, yy, value, 9, align="right")
        yy -= 13

    y = min(y, yy) - 20
    doc.text(40, y, "Bill to" if is_invoice else "Prepared for", 9, bold=True, color=(0.35, 0.38, 0.45))
    y -= 14
    if account is not None:
        doc.text(40, y, account.name, 11, bold=True)
        y -= 13
        addr = account.data.get("billing_address")
        if addr:
            f = meta.fields.get("account")
            _ = f
            doc.text(40, y, display_text(svc.registry.get("account").fields["billing_address"], addr), 9)
            y -= 12
        if account.data.get("abn"):
            doc.text(40, y, f"ABN {account.data['abn']}", 9)
            y -= 12
    if contact is not None:
        doc.text(40, y, f"Attn: {contact.name}", 9)
        y -= 12
    if not is_invoice and record.data.get("title"):
        y -= 6
        doc.text(40, y, str(record.data["title"]), 11, bold=True)
        y -= 6

    y -= 18
    cols = [
        (40, "Description", "left"),
        (330, "Qty", "right"),
        (400, "Unit price", "right"),
        (465, "GST", "right"),
        (w - 40, "Amount", "right"),
    ]

    def header(yh: float) -> None:
        doc.rect(36, yh - 6, w - 72, 20, (0.95, 0.96, 0.98))
        for x, label, align in cols:
            doc.text(x, yh, label, 9, bold=True, align=align)

    header(y)
    y -= 22
    for line in lines:
        if y < 150:
            doc.new_page()
            y = h - 60
            header(y)
            y -= 22
        desc = str(line.data.get("description") or line.name)[:60]
        qty = to_decimal(line.data.get("quantity")) or Decimal(0)
        doc.text(40, y, desc, 9)
        doc.text(330, y, f"{qty.normalize():f}", 9, align="right")
        doc.text(400, y, _money(line.data.get("unit_price")), 9, align="right")
        doc.text(465, y, _money(line.data.get("tax_amount")), 9, align="right")
        doc.text(w - 40, y, _money(line.data.get("line_total")), 9, align="right")
        if line.data.get("discount"):
            y -= 11
            doc.text(48, y, f"Discount {_money(line.data.get('discount'))}", 8, color=(0.4, 0.42, 0.48))
        y -= 8
        doc.line(40, y, w - 40, y)
        y -= 14

    y -= 6
    totals: list[tuple[str, Any]] = [
        (
            "Subtotal (ex GST)",
            money(to_decimal(record.data.get("subtotal")) or 0)
            - money(to_decimal(record.data.get("discount_total")) or 0),
        ),
        ("GST", record.data.get("tax_total")),
        ("Total (inc GST)", record.data.get("total")),
    ]
    if is_invoice:
        totals += [
            ("Amount paid", record.data.get("amount_paid")),
            ("Balance due", record.data.get("balance")),
        ]
    for label, value in totals:
        bold = label.startswith(("Total", "Balance"))
        doc.text(w - 140, y, label, 10 if bold else 9, bold=bold, align="right")
        doc.text(w - 40, y, _money(value), 10 if bold else 9, bold=bold, align="right")
        y -= 15

    y -= 20
    footer = str(billing.get("invoice_footer") or "") if is_invoice else str(record.data.get("terms") or "")
    for chunk in [footer[i : i + 100] for i in range(0, len(footer), 100)][:8]:
        doc.text(40, y, chunk, 9, color=(0.35, 0.38, 0.45))
        y -= 12
    if is_invoice and billing.get("bank_details"):
        doc.text(40, y - 4, f"Payment details: {billing['bank_details']}"[:110], 9)
    doc.text(40, 30, f"{seller} - {title} {number}", 8, color=(0.55, 0.58, 0.64))
    return doc.render()

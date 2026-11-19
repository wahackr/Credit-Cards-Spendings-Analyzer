"""Hand-built PDFs for tests, so no PDF writer library is needed as a dependency."""

ROWS = [
    ("02/11", "APPLE PAYSUBSCR PSE *IPHONE", "1,198.00", "1,198.00"),
    ("03/11", "HKETOLL HKE SERVICES LTD", "47.50", "47.50"),
    ("04/11", "OKLOKOTOKO EXPRESS LTD", "128.00", "128.00"),
    ("05/11", "CITY U AC1 CW", "36.00", "36.00"),
    ("06/11", "DIGITALOCEAN.COM INC", "1,204.55", "1,204.55"),
    ("07/11", "OCTOPUS ADS OCTOPUS HKLTD", "65.00", "65.00"),
    ("08/11", "HUTCHISON TELECOMS TOPUP", "98.00", "98.00"),
    ("09/11", "DECATHLON HONG KONG LTD", "459.00", "459.00"),
    ("10/11", "PHYSICAL FITN GYM", "750.00", "750.00"),
    ("11/11", "YF LIFE INSURANCE PREMIUM", "2,340.00", "2,340.00"),
]

COLUMN_X = [50, 110, 330, 430]
PAGE_WIDTH = 595
PAGE_HEIGHT = 400


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _text_stream(instructions: list[str]) -> str:
    return "BT /F1 8 Tf\n" + "\n".join(instructions) + "\nET"


def _text_at(x: float, y: float, text: str) -> str:
    return f"1 0 0 1 {x:g} {y:g} Tm ({_escape(text)}) Tj"


def build_pdf(content_stream: str, extra_objects: list[str] = ()) -> bytes:
    """Assemble a one-page PDF with the given content stream and correct xrefs."""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content_stream)} >>\nstream\n{content_stream}\nendstream",
        *extra_objects,
    ]

    pdf = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf.encode()))
        pdf += f"{number} 0 obj\n{body}\nendobj\n"

    xref_offset = len(pdf.encode())
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    return pdf.encode()


def statement_pdf() -> bytes:
    """Borderless transaction table: date, description, and two amount columns."""
    y = PAGE_HEIGHT - 40
    instructions = [
        _text_at(COLUMN_X[0], y, "Date"),
        _text_at(COLUMN_X[1], y, "Description"),
        _text_at(COLUMN_X[2], y, "Amount USD"),
        _text_at(COLUMN_X[3], y, "Amount HKD"),
    ]
    y -= 16
    for date, description, usd, hkd in ROWS:
        instructions.append(_text_at(COLUMN_X[0], y, date))
        instructions.append(_text_at(COLUMN_X[1], y, description))
        instructions.append(_text_at(COLUMN_X[2], y, usd))
        instructions.append(_text_at(COLUMN_X[3], y, hkd))
        y -= 16
    instructions.append(_text_at(COLUMN_X[0], y - 10, "Total HKD: 7,773.05"))
    return build_pdf(_text_stream(instructions))


def scanned_pdf() -> bytes:
    """A page with no text at all, standing in for a scanned statement."""
    return build_pdf("0 0 400 300 re f")

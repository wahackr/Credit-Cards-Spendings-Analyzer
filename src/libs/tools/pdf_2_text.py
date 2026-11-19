"""
Statement PDF to Markdown text converter

Text extraction replaces the old PDF-to-image path: table columns are rebuilt from
word coordinates (via markitdown/pdfplumber), so amounts reach the model as exact
characters instead of pixels.
"""

import io
import os
import re
from dataclasses import dataclass
from typing import List

from markitdown import MarkItDown, StreamInfo

MIN_STATEMENT_TEXT_CHARS = 120
"""Extracted text below this length means the PDF has no usable text layer."""

AMOUNT_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?![\d.])")
"""Money-shaped tokens such as 1,198.00 or 47.50."""


class StatementTextError(ValueError):
    """Raised when a PDF cannot be turned into statement text."""


@dataclass(frozen=True)
class StatementText:
    filename: str
    markdown: str

    @property
    def char_count(self) -> int:
        return len(self.markdown)

    @property
    def table_rows(self) -> int:
        """Rows the converter recognised as table rows."""
        return sum(1 for line in self.markdown.splitlines() if line.lstrip().startswith("|"))

    @property
    def amount_tokens(self) -> int:
        """Money-shaped tokens available to analyze."""
        return len(AMOUNT_PATTERN.findall(self.markdown))

    def __str__(self) -> str:
        return self.markdown


def extract_statement_text(pdf_bytes: bytes, *, filename: str = "statement.pdf") -> StatementText:
    """
    Convert PDF bytes into Markdown statement text.

    Args:
        pdf_bytes: Raw PDF content
        filename: Name used in messages and to identify the document

    Returns:
        StatementText holding the Markdown text and extraction stats

    Raises:
        StatementTextError: If the PDF cannot be read or has no usable text layer
    """
    try:
        result = MarkItDown().convert(
            io.BytesIO(pdf_bytes),
            stream_info=StreamInfo(extension=".pdf", mimetype="application/pdf", filename=filename),
        )
    except Exception as error:
        raise StatementTextError(f"Could not read {filename}: {error}") from error

    markdown = (result.markdown or "").strip()
    if len(markdown) < MIN_STATEMENT_TEXT_CHARS:
        raise StatementTextError(
            f"{filename} has no usable text layer ({len(markdown)} characters extracted). "
            "Scanned or image-only statements need a text PDF export; OCR is not supported."
        )

    return StatementText(filename=filename, markdown=markdown)


def get_pdf_files(folder_path: str) -> List[str]:
    """
    Get a list of all PDF files in the specified folder.

    Args:
        folder_path: Path to the folder to search for PDF files

    Returns:
        List of PDF file paths
    """
    pdf_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

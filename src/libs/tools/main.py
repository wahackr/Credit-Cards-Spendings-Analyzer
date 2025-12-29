"""
PDF to Image Converter Module

This module provides utilities to convert PDF files to images.
"""

import os
from pathlib import Path
from typing import List, Optional

from pdf2image import convert_from_path


def convert_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    fmt: str = 'png',
    verbose: bool = True
) -> List[str]:
    """
    Convert PDF pages to individual image files.

    Args:
        pdf_path: Path to the PDF file to convert
        output_dir: Directory where images will be saved
        dpi: Resolution for the output images (default: 300)
        fmt: Image format - 'jpeg', 'png', etc. (default: 'jpeg')
        verbose: Print progress messages (default: True)

    Returns:
        List of paths to the saved image files

    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        Exception: If conversion fails
    """
    # Validate PDF path
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"Starting conversion of {pdf_path}...")

    try:
        # Convert PDF pages to a list of PIL Image objects
        pages = convert_from_path(pdf_path, dpi=dpi, fmt=fmt)

        if verbose:
            print(f"Found {len(pages)} pages. Saving each page as an image...")

        saved_paths = []

        # Iterate over the pages and save each one individually
        for i, page in enumerate(pages):
            # Create a filename for each image
            image_filename = f'page_{i + 1}.{fmt.lower()}'
            image_path = output_path / image_filename

            # Save the image
            page.save(str(image_path), fmt.upper())
            saved_paths.append(str(image_path))

            if verbose:
                print(f"Saved: {image_path}")

        if verbose:
            print(f"Conversion successful! All {len(pages)} pages saved to '{output_dir}'")
            print("================================================================")

        return saved_paths

    except Exception as e:
        error_msg = f"An error occurred during conversion: {e}"
        if verbose:
            print(error_msg)
            print("Ensure Poppler is correctly installed and accessible in your system's PATH.")
            print("================================================================")
        raise


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


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the number of pages in a PDF file without converting to images.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Number of pages in the PDF

    Raises:
        FileNotFoundError: If the PDF file doesn't exist
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages = convert_from_path(pdf_path, dpi=72)  # Low DPI for speed
    return len(pages)


def convert_pdf_page_to_image(
    pdf_path: str,
    page_number: int,
    output_path: Optional[str] = None,
    dpi: int = 300,
    fmt: str = 'jpeg'
) -> str:
    """
    Convert a specific page of a PDF to an image.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number to convert (1-indexed)
        output_path: Optional path for the output image
        dpi: Resolution for the output image (default: 300)
        fmt: Image format - 'jpeg', 'png', etc. (default: 'jpeg')

    Returns:
        Path to the saved image file

    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        ValueError: If page_number is invalid
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if page_number < 1:
        raise ValueError("Page number must be >= 1")

    # Convert only the specified page
    pages = convert_from_path(
        pdf_path,
        dpi=dpi,
        fmt=fmt,
        first_page=page_number,
        last_page=page_number
    )

    if not pages:
        raise ValueError(f"Page {page_number} not found in PDF")

    # Determine output path
    if output_path is None:
        pdf_name = Path(pdf_path).stem
        output_path = f"{pdf_name}_page_{page_number}.{fmt.lower()}"

    # Save the image
    pages[0].save(output_path, fmt.upper())

    return output_path

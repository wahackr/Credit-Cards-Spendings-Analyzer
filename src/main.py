import logging
import os

from libs.gemini.main import init_gemini_client, read_images
from libs.tools.pdf_2_image import convert_pdf_to_images, get_pdf_files
from libs.tools.state_2_csv import statement_to_csv
from libs.tools.statement_reader import read_statement

# logging.basicConfig(level=logging.DEBUG)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3-flash-preview"

pdf_folder = f"{os.getcwd()}/statements"
pdf_files = get_pdf_files(pdf_folder)

print("PDF Files Found:")
pdf_images = []

statement_rows = "date,transaction_name,amount,category,account,card_name\n"

for pdf in pdf_files:

    print(pdf)
    # 1. convert pdf to images
    output_path = f"{pdf.replace(".pdf", "")}/images"
    pdf_images = convert_pdf_to_images(pdf, output_path, fmt="png")

    # 2. send pdf images to gemini for analysis
    print("Files to be sent to Gemini:")
    for img in pdf_images:
        print(img)

    # direct call Gemini API
    # gemini_client = init_gemini_client(GEMINI_API_KEY)
    # response = read_images(gemini_client, GEMINI_MODEL, pdf_images)

    # or via LangChain wrapper
    response = read_statement(GEMINI_API_KEY, GEMINI_MODEL, pdf_images)

    statement_rows += statement_to_csv(response)

    print(f"Statement {output_path} done")
    print("----------------------------------------------------------------")

print("CSV Output:")
print(statement_rows)

import os

from libs.llm.main import load_llm_config
from libs.tools.pdf_2_image import convert_pdf_to_images, get_pdf_files
from libs.tools.state_2_csv import statement_to_csv
from libs.tools.statement_reader import read_statement

# logging.basicConfig(level=logging.DEBUG)

try:
    llm_config = load_llm_config()
except ValueError as error:
    raise SystemExit(f"Configuration error: {error}") from error

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

    # 2. send PDF images to the configured provider for analysis
    print(f"Files to be sent to {llm_config.provider} ({llm_config.model}):")
    for img in pdf_images:
        print(img)

    response = read_statement(llm_config, pdf_images)

    statement_rows += statement_to_csv(response)

    print(f"Statement {output_path} done")
    print("----------------------------------------------------------------")

print("CSV Output:")
print(statement_rows)

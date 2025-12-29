import os

from libs.gemini.main import init_gemini_client, read_images
from libs.tools.main import convert_pdf_to_images, get_pdf_files

""" 
pdf_folder = f"{os.getcwd()}/statements"
pdf_files = get_pdf_files(pdf_folder)

print("PDF Files Found:")
pdf_images = []
for pdf in pdf_files:
    print(pdf)
    output_path = f"{pdf.replace(".pdf", "")}/images"
    pdf_images += (convert_pdf_to_images(pdf, output_path, fmt="png"))

 """
pdf_images = [
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/ae-2025-12-20/images/page_1.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/ae-2025-12-20/images/page_2.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/ae-2025-12-20/images/page_3.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/ae-2025-12-20/images/page_4.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/ae-2025-12-20/images/page_5.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/ae-2025-12-20/images/page_6.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/hsbc-red-202512/images/page_1.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/hsbc-red-202512/images/page_2.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/hsbc-red-202512/images/page_3.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/hsbc-red-202512/images/page_4.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/scb-202512/images/page_1.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/scb-202512/images/page_2.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/scb-202512/images/page_3.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/scb-202512/images/page_4.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/scb-202512/images/page_5.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/citi-202512/images/page_1.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/citi-202512/images/page_2.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/citi-202512/images/page_3.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/citi-202512/images/page_4.png",
    "/workspaces/Credit-Cards-Spendings-Analysiser/statements/citi-202512/images/page_5.png"
]

gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_client = init_gemini_client(gemini_api_key)

print("Files to be sent to Gemini:")
for img in pdf_images:
    print(img)

response = read_images(gemini_client, pdf_images)

print("Gemini Response:")
print(response)

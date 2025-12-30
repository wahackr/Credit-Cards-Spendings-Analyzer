from google import genai
from langchain.messages import HumanMessage
from prompts.main import STATEMENT_READER_INSTUCTIONS
from states.main import Statement

from libs.gemini.main import init_langchain_model


def read_statement(gemini_api_key: str, gemini_model: str, image_paths: list[str]) -> Statement:

    # Init model
    model = init_langchain_model(gemini_api_key, gemini_model)

    # Set up structured output model
    structured_output_model = model.with_structured_output(Statement)

    # Upload and wait for processing
    client = genai.Client()
    uploaded_files = []
    for file in image_paths:
        uploaded_file = client.files.upload(file=file)
        uploaded_files.append({
            "type": "file",
            "file_id": uploaded_file.uri,
            "mime_type": "image/png",
        })

    content = [{"type": "text", "text": STATEMENT_READER_INSTUCTIONS}
               ] + uploaded_files

    message = HumanMessage(content=content)

    response = structured_output_model.invoke([message])

    return response

from google import genai as new_genai
from langchain_google_genai import ChatGoogleGenerativeAI

from libs.prompts.main import STATEMENT_READER_INSTUCTIONS


def init_gemini_client(api_key):
    """Initialize Gemini client"""
    try:
        # Create and return the new client with the API key
        return new_genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return None


def read_images(gemini_client, gemini_model, image_paths):

    upload_files = []

    for file in image_paths:
        upload_files.append(gemini_client.files.upload(file=file))

    # Create the prompt with text and multiple images
    response = gemini_client.models.generate_content(

        model=gemini_model,
        contents=[STATEMENT_READER_INSTUCTIONS] + upload_files
    )

    return response.text


def init_langchain_model(api_key: str, model: str):
    """Initialize the LLM for classification"""
    return ChatGoogleGenerativeAI(
        api_key=api_key,
        model=model
    )

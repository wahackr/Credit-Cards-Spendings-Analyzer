import base64
import mimetypes
from pathlib import Path

from google import genai
from langchain.messages import HumanMessage

from libs.llm.main import GEMINI, LLMConfig, create_chat_model
from libs.prompts.main import STATEMENT_READER_INSTUCTIONS
from libs.states.main import Statement


def _image_data_url(image_path: str) -> str:
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _inline_image_content(image_paths: list[str]) -> list[dict]:
    content = [{"type": "text", "text": STATEMENT_READER_INSTUCTIONS}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": _image_data_url(image_path)},
        }
        for image_path in image_paths
    )
    return content


def _gemini_file_content(image_paths: list[str]) -> list[dict]:
    client = genai.Client()
    uploaded_files = []
    for file in image_paths:
        uploaded_file = client.files.upload(file=file)
        uploaded_files.append(
            {
                "type": "file",
                "file_id": uploaded_file.uri,
                "mime_type": "image/png",
            }
        )

    content = [
        {"type": "text", "text": STATEMENT_READER_INSTUCTIONS},
        *uploaded_files,
    ]
    return content


def read_statement(
    config: LLMConfig,
    image_paths: list[str],
) -> Statement | None:
    """Read statement images, returning None when no structured call is made."""
    if not image_paths:
        raise ValueError("At least one statement image is required.")

    model = create_chat_model(config)
    structured_output_model = model.with_structured_output(Statement)

    content = (
        _gemini_file_content(image_paths)
        if config.provider == GEMINI
        else _inline_image_content(image_paths)
    )
    response = structured_output_model.invoke([HumanMessage(content=content)])

    if response is not None:
        print("=" * 64)
        print(f"Structured LLM response ({config.provider} / {config.model}):")
        print(response.model_dump_json(indent=2))
        print("=" * 64)
    return response

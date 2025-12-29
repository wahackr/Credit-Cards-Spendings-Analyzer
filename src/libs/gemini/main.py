from google import genai as new_genai


def init_gemini_client(api_key):
    """Initialize Gemini client"""
    try:
        # Create and return the new client with the API key
        return new_genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return None


def read_images(gemini_client, image_paths):

    upload_files = []

    for file in image_paths:
        upload_files.append(gemini_client.files.upload(file=file))

    # Create the prompt with text and multiple images
    response = gemini_client.models.generate_content(

        model="gemini-3-flash-preview",
        contents=[
            """
            Analyze the credit card statments, list out all the transactions with date, merchant and amount. Payment credits can be ignored.
            Some statments may incluing the original currency and amount, but please always use the HKD column for analysis.
            Some statments may use more than 1 lines for a single transaction, please make sure to capture all lines for each transaction.
            Put all credit card transactions in a table format with columns Date, Merchant, Amount, Card and Category.
            Category should be one of the following: Dining, Entertainment, Travel, Cloud, Utilities, Health, Shopping, Fuel, Insurance, Telecom, Others.
            For HSBC credit cards, since the statment may be hard to read, please make sure to capture all transactions, you may sum up the total spending and cross check with the statment total to ensure all transactions are captured.
            """,
        ] + upload_files
    )

    return response.text

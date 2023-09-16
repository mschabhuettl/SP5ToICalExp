from PyPDF2 import PdfReader


def convert_pdf_to_text(file_path: str) -> str:
    """
    Converts a PDF file to text.

    Parameters:
        file_path (str): The path to the PDF file.

    Returns:
        str: The text content of the PDF.
    """
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"An error occurred while reading the PDF: {str(e)}")
        return ""

    text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text is not None:
            text.append(page_text)

    return "\n".join(text)

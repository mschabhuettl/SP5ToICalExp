# Standard Library imports
import os
import pickle
import re
import tempfile
import uuid
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union
from zipfile import ZipFile, ZIP_DEFLATED

# Third-Party imports
from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for
from slugify import slugify
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

# Local imports
from utils.pdf_to_text import convert_pdf_to_text
from utils.text_to_ical import convert_shifts_to_ical

# Setup logging
logging.basicConfig(level=logging.INFO)

# Constants
ERROR_FLASH_CATEGORY = 'error'  # Category used for flashing error messages
TEMP_DIR = '/tmp/'  # Temporary directory for file storage
ZIP_EXTENSION = '.zip'  # File extension for ZIP files

bp = Blueprint('views', __name__)


def process_uploaded_file(file):
    """
    Processes the uploaded file and returns the extracted text and statistics.

    Parameters:
    - file: The uploaded file object

    Returns:
    - tuple: persons_data, stats if the file is processed successfully, None, None otherwise.
    """
    file_path = save_uploaded_file(file)
    if not file_path:
        return None, None

    try:
        # Convert PDF to text
        extracted_text = convert_pdf_to_text(file_path)
    except FileNotFoundError as e:
        flash(f"An error occurred during file processing: {str(e)}", ERROR_FLASH_CATEGORY)
        return None, None

    # Process the extracted text and generate statistics
    return process_text_and_generate_stats(extracted_text)


@bp.route("/", methods=['GET', 'POST'])
def home():
    """
    Handles the home route ("/").

    If the request method is GET, renders the home page.
    If the request method is POST, it:
        - Takes an uploaded file from the user
        - Processes the file to extract textual content
        - Processes the extracted text to generate persons_data and statistics
        - Renders the home page along with the processed data and statistics

    Returns:
    - HTML: Rendered template with any available data and statistics
    """

    # Initialize variables
    persons_data = None
    stats = None
    extracted_text = None

    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            persons_data, stats = process_uploaded_file(file)

    return render_template(
        'index.html',
        persons_data=persons_data,
        stats=stats,
        debug_text=extracted_text
    )


@bp.route("/download")
def download():
    """
    Handles the download route ("/download").

    - Retrieves the temporary filename from the user's session
    - Loads iCal contents from the corresponding temporary file
    - Creates a ZIP file containing these iCal contents
    - Sends this ZIP file to the user as a downloadable attachment

    If any step fails, redirects the user to the home page and flashes an error message.

    Returns:
    - ZIP File: Sends a ZIP file as an attachment if successful
    - Redirect: Redirects to the home page if any error occurs
    """
    try:
        # Retrieve the temporary filename from the session
        temp_filename = session.get('temp_filename')
        if not temp_filename:
            raise FileNotFoundError("Session does not contain a temporary filename.")

        # Load iCal contents from the temporary file
        ical_contents = load_ical_contents_from_temp_file(temp_filename)
        if not ical_contents:
            raise ValueError("No iCal content found in the temporary file.")

        # Generate a unique download ID and create a ZIP file
        download_id = uuid.uuid4()
        zip_path = tempfile.mktemp(suffix=".zip")
        create_zip_from_ical_contents(ical_contents, zip_path)

        # Check if the ZIP file was created successfully
        if not zip_path:
            raise FileNotFoundError("Failed to create ZIP file.")

        # Send the ZIP file as an attachment
        return send_file(zip_path, as_attachment=True, download_name='shifts.zip')

    except (FileNotFoundError, ValueError) as e:
        # Log the error for debugging purposes
        logging.error(f"An error occurred during file download: {e}")

        # Display an error message and redirect to the home page
        flash(f"Error: {e}", ERROR_FLASH_CATEGORY)
        return redirect(url_for('views.home'))


@bp.route("/download/<string:person_name>")
def download_individual(person_name: str):
    """
    Handles the download of individual ICS files.

    - Retrieves the temporary filename from the user's session
    - Loads iCal contents of the specified person from the temporary file
    - Creates an ICS file from these contents
    - Sends this ICS file to the user as a downloadable attachment

    If any step fails, redirects the user to the home page and flashes an error message.

    Parameters:
    - person_name (str): The name of the person whose shifts are to be downloaded.

    Returns:
    - ICS File: Sends an ICS file as an attachment if successful
    - Redirect: Redirects to the home page if any error occurs
    """
    try:
        # Retrieve the temporary filename from the session
        temp_filename = session.get('temp_filename')
        if not temp_filename:
            raise FileNotFoundError("Session does not contain a temporary filename.")

        # Load iCal contents from the temporary file
        with open(temp_filename, 'rb') as tempf:
            ical_contents = pickle.load(tempf)

        if not ical_contents:
            raise ValueError("No iCal content found in the temporary file.")

        # Validate the person_name
        if person_name not in ical_contents:
            raise KeyError(f"No data found for the specified person: {person_name}")

        # Prepare individual ICS content and file path
        ical_content = ical_contents[person_name]
        download_id = uuid.uuid4()
        filename = create_slugified_filename(person_name)
        ics_path = tempfile.mktemp(suffix=".ics")

        # Write the individual ICS content to the file
        with open(ics_path, 'wb') as icsf:
            icsf.write(ical_content.encode())

        return send_file(ics_path, as_attachment=True, download_name=f"{filename}.ics")

    except (FileNotFoundError, ValueError, KeyError) as e:
        logging.error(f"An error occurred during individual file download: {e}")
        flash(f"Error: {e}", ERROR_FLASH_CATEGORY)
        return redirect(url_for('views.home'))

    finally:
        if 'ics_path' in locals() and os.path.exists(ics_path):
            os.remove(ics_path)


# Utility functions
def german_to_english_weekday(date_string):
    """Convert German weekdays to English.

    Parameters:
        date_string (str): The date string containing German weekdays.

    Returns:
        str: The date string with German weekdays converted to English.
    """

    # Mapping of German weekdays to English weekdays
    replacements = {
        'Mo.': 'Mon.',
        'Di.': 'Tue.',
        'Mi.': 'Wed.',
        'Do.': 'Thu.',
        'Fr.': 'Fri.',
        'Sa.': 'Sat.',
        'So.': 'Sun.'
    }

    # Replace German weekdays with English weekdays
    for german, english in replacements.items():
        date_string = date_string.replace(german, english)

    return date_string


def normalize_entry(entry):
    """Normalize an entry according to specified rules.

    Args:
        entry (str): The original entry string.

    Returns:
        str: The normalized entry string.
    """

    # Remove trailing zeros (e.g., "ILL0" becomes "ILL")
    entry = re.sub(r'0$', '', entry)

    # Remove time range indicators (e.g., "TRAIN 8-16" becomes "TRAIN")
    entry = re.sub(r'\s?\d{1,2}-\d{1,2}', '', entry)

    # Remove trailing numbers (e.g., "QUALITYM 12" becomes "QUALITYM")
    entry = re.sub(r'\s?\d+$', '', entry)

    # Remove any extra white spaces and return
    return entry.strip()


def process_line(line):
    """Process individual lines from the extracted text."""
    # Patterns for regular and all-day events
    pattern_regular = re.compile(
        r"(?P<date>[A-Za-z]+\.\s\d{2}\.\d{2}\.\d{4})\s(?P<time>\d{2}:\d{2}-\d{2}:\d{2})\s(?P<hours>\d{1,2},\d{2})(?P<entry>.*?)(?=Zeitraum|$)"
    )
    pattern_all_day = re.compile(
        r"(?P<date>[A-Za-z]+\.\s\d{2}\.\d{2}\.\d{4})\sGanztägig\s(?P<hours>\d{1,2},\d{2})(?P<entry>.*?)(?=Zeitraum|$)"
    )

    # Check for matches
    match = pattern_regular.search(line) or pattern_all_day.search(line)

    return match.groupdict() if match else None


def process_extracted_text(text):
    """Process extracted text to capture relevant shift information.

    Parameters:
        text (str): The raw text containing shift details.

    Returns:
        list: A list of dictionaries containing processed shift details.
    """

    # Initialize an empty list to store shift details
    shifts = []

    # Process each line in the input text
    for line in text.split("\n"):
        processed_line = process_line(line)
        if processed_line:
            # Extract details
            date = german_to_english_weekday(processed_line.get("date", ""))
            shift_time = processed_line.get("time", "All Day")
            hours = processed_line.get("hours", "N/A")

            # Determine if it's an all-day event
            is_all_day = shift_time == "All Day"

            # Remove time from entry, if present
            entry = processed_line.get("entry", "").strip()
            if not is_all_day:
                entry = re.sub(r'\d{1,2}:\d{2}-\d{1,2}:\d{2}', '', entry).strip()

            # Normalize the entry based on the specified rules
            entry = normalize_entry(entry)

            # Add processed details to shifts
            shifts.append({
                "date": date,
                "shift_time": shift_time,
                "hours": hours,
                "entry": entry,
                "all_day": is_all_day
            })

    return shifts


def save_uploaded_file(file: FileStorage) -> Optional[str]:
    """
    Saves the uploaded file to the server's file system.

    - Checks if the uploaded file exists and is of a valid type
    - Generates a secure filename and determines the path for saving
    - Saves the file to the specified path

    Parameters:
    - file (FileStorage): The uploaded file object from the Flask request

    Returns:
    - str: The path to the saved file if successful
    - None: None if saving fails for any reason, while setting an error flash message
    """
    try:
        # Check if a file is uploaded
        if file is None:
            flash('No file part', ERROR_FLASH_CATEGORY)
            return None

        filename = file.filename

        # Check if a file is selected
        if not filename:
            flash('No selected file', ERROR_FLASH_CATEGORY)
            return None

        # Check if the uploaded file has an allowed extension
        if not allowed_file(filename):
            flash('File type not allowed', ERROR_FLASH_CATEGORY)
            return None

        # Secure the filename and save the file
        secure_name = secure_filename(filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, secure_name)

        file.save(file_path)

        return file_path

    except FileNotFoundError:
        flash("The specified upload folder does not exist", ERROR_FLASH_CATEGORY)
        return None
    except PermissionError:
        flash("Permission denied while saving the file", ERROR_FLASH_CATEGORY)
        return None
    except Exception as e:
        flash(f"An unexpected error occurred while saving the file: {str(e)}", ERROR_FLASH_CATEGORY)
        return None


def process_text_and_generate_stats(extracted_text: str) -> Tuple[Optional[List[Dict]], Optional[Dict]]:
    """
    Processes the extracted text to generate individual shift data and overall statistics.

    - Invokes functions to process the text and create statistics
    - Saves the generated iCal content to a temporary file

    Parameters:
    - extracted_text (str): The raw text extracted from the uploaded file

    Returns:
    - Tuple: A tuple containing the persons_data list and the statistics dictionary
        - persons_data: List of dictionaries, each containing shift data for a person
        - stats: Dictionary containing statistical information about shifts
    """
    persons_data = None
    stats = None

    try:
        # Process the extracted text for multiple persons
        persons_data = process_multiple_persons_text(extracted_text)
        if persons_data is None:
            raise ValueError("Failed to process the extracted text.")

        # Generate statistics based on the processed data
        stats = create_shift_statistics(persons_data)
        if stats is None:
            raise ValueError("Failed to create shift statistics.")

        # Generate iCal contents and save to a temporary file
        ical_contents = create_ical_contents(persons_data)
        if ical_contents is None:
            raise ValueError("Failed to create iCal contents.")

        save_ical_to_tempfile(ical_contents)

    except ValueError as ve:
        logging.error(f"An error occurred: {ve}")
        # Optionally, you could add a flash message here for UI feedback

    return persons_data, stats


def create_ical_contents(persons_data: Dict[str, List[Any]]) -> Optional[Dict[str, str]]:
    """
    Generates iCal data for each person based on their shift data.

    Parameters:
    - persons_data (Dict[str, List[Any]]): A dictionary containing each person's name as a key
                                           and a list of their shifts as the corresponding value.

    Returns:
    - Optional[Dict[str, str]]: A dictionary with each person's name as a key and their
                                 corresponding iCal data as the value. Returns None if
                                 persons_data is empty or None.
    """
    if not persons_data:
        return None

    ical_contents = {}

    try:
        for person, shifts in persons_data.items():
            # Generate iCal data for each person using their shift information
            ical_data = convert_shifts_to_ical([shifts])

            if ical_data is None:
                raise ValueError(f"Failed to generate iCal data for {person}")

            ical_contents[person] = ical_data

    except Exception as e:
        logging.error(f"An error occurred while generating iCal contents: {e}")
        return None

    return ical_contents


def save_ical_to_tempfile(ical_contents: Dict[str, str]) -> Optional[str]:
    """
    Save iCal content to a temporary file and store the filename in the session.

    Parameters:
    - ical_contents (Dict[str, str]): Dictionary containing iCal data for each person.

    Returns:
    - Optional[str]: The name of the temporary file, or None if saving fails.
    """
    try:
        if not ical_contents:
            raise ValueError("The ical_contents parameter cannot be empty or None.")

        # Create and save the temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tempf:
            pickle.dump(ical_contents, tempf)

        # Store the temporary filename in the session
        session['temp_filename'] = tempf.name
        return tempf.name

    except Exception as e:
        logging.error(f"An error occurred while saving the temporary iCal file: {e}")
        return None


class TempFileReadError(Exception):
    """
    Exception raised when reading from a temporary file fails.

    Attributes:
        message -- explanation of the error
        filename -- name of the file causing the error
    """

    def __init__(self, message: str, filename: str = None):
        self.message = message
        self.filename = filename
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}. Filename: {self.filename}" if self.filename else self.message


def load_ical_contents_from_temp_file(temp_filename: str) -> Optional[Dict[str, Any]]:
    """
    Load iCal contents from a temporary file.

    Parameters:
    - temp_filename (str): The name of the temporary file to read from.

    Returns:
    - Optional[Dict[str, Any]]: The iCal contents loaded from the file, or None if loading fails.

    Raises:
    - TempFileReadError: If any error occurs while reading the temporary file.
    """
    try:
        with open(temp_filename, 'rb') as tempf:
            return pickle.load(tempf)
    except (FileNotFoundError, pickle.UnpicklingError, EOFError) as e:
        logging.error(f"An error occurred while reading the temporary file {temp_filename}: {str(e)}")
        raise TempFileReadError(f"An error occurred while reading the temporary file {temp_filename}") from e


def create_zip_from_ical_contents(ical_contents: Dict[str, str], download_id: Union[str, int]) -> str:
    """
    Create a ZIP file from iCal content and returns its path.

    Parameters:
    - ical_contents (Dict[str, str]): A dictionary mapping person names to their iCal content.
    - download_id (Union[str, int]): A unique identifier for the download.

    Returns:
    - str: The path to the created ZIP file.

    Raises:
    - Exception: If any error occurs during the ZIP file creation.
    """
    try:
        zip_path = f'{TEMP_DIR}{download_id}{ZIP_EXTENSION}'

        # Using ZipFile context manager to automatically close the file
        with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zipf:
            for name, ical_content in ical_contents.items():
                # Create a slugified filename without the extension
                filename_without_extension = create_slugified_filename(name)

                # Add the file extension '.ics' here
                filename_with_extension = f"{filename_without_extension}.ics"

                zipf.writestr(filename_with_extension, ical_content.encode())

        return zip_path

    except (FileNotFoundError, PermissionError) as e:
        logging.error(f"An error occurred while creating the ZIP file: {e}")
        # If required, you can raise an exception here for the caller to handle
        raise


def send_and_cleanup(zip_path, temp_filename):
    """Sends the ZIP file as an attachment and cleans up the temporary files.

    Parameters:
    - zip_path: str
        The path of the ZIP file to be sent.
    - temp_filename: str
        The temporary filename to be cleaned up.

    Returns:
    - Response object from Flask's send_file if successful.
    """

    try:
        if not zip_path or not temp_filename:
            logging.error("Missing file paths for sending and cleaning up.")
            raise ValueError("Both zip_path and temp_filename must be provided.")

        # Sends the ZIP file as an attachment.
        return send_file(zip_path, as_attachment=True, download_name='shifts.zip')

    except Exception as e:
        logging.error(f"An error occurred while sending the ZIP file: {e}")
        # Optionally, raise an exception for the caller to handle.
        raise

    finally:
        # Cleans up the temporary files.
        cleanup_files([zip_path, temp_filename])


def cleanup_files(file_paths):
    """Removes the specified files from the file system.

    Parameters:
    - file_paths: list of str
        The list of file paths to be removed.

    """
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Successfully deleted: {file_path}")

        except Exception as e:
            logging.error(f"An error occurred while deleting the file {file_path}: {e}")


# Additional helper functions
def format_name(name):
    """Formats a name to standard 'Last, First' with a space after the comma.

    Parameters:
        name (str): The name to be formatted, expected in 'Last, First' format.

    Returns:
        str: The formatted name in 'Last, First' format.

    Raises:
        TypeError: If the input is not a string.
        ValueError: If the input string is not in the 'Last, First' format
                    or either last name or first name are empty.

    Examples:
        >>> format_name("Doe,John")
        "Doe, John"
        >>> format_name("Doe , John")
        "Doe, John"
        >>> format_name("  Doe,John  ")
        "Doe, John"

    """
    if not isinstance(name, str):
        raise TypeError("The input should be a string.")

    # Split the input name into last and first names
    name_parts = name.split(',', 1)

    # Validate the name format
    if len(name_parts) != 2:
        raise ValueError("The input name should be in the 'Last, First' format.")

    # Strip any leading/trailing whitespaces from each name part
    last_name, first_name = [part.strip() for part in name_parts]

    # Ensure both names are non-empty
    if not last_name or not first_name:
        raise ValueError("Both last name and first name should be non-empty.")

    return f"{last_name}, {first_name}"


def create_individual_temp_file(ical_content, person_name):
    """Creates and saves a temporary file containing individual iCal content.

    Parameters:
        ical_content (str): The iCal content to be stored in the file.
        person_name (str): The name of the person for whom the iCal content is generated.

    Returns:
        str: The name of the created temporary file.

    Examples:
        >>> create_individual_temp_file("BEGIN:VCALENDAR...END:VCALENDAR", "John")
        "individual_John.temp"

    Notes:
        - The temporary file will be in binary write mode ('wb') because we are using pickle.
        - Always remember to remove temporary files after they have been used to avoid clutter.
    """

    # Generate a unique temporary filename for the individual download
    temp_file_name = f"individual_{person_name}.temp"

    # Open the temporary file in binary write mode ('wb') and save the ical_content
    with open(temp_file_name, 'wb') as f:
        pickle.dump(ical_content, f)

    return temp_file_name


def normalize_name(name):
    """Normalizes a name by removing any "(Forts.)" suffix from it.

    Parameters:
        name (str): The original name that may contain a "(Forts.)" suffix.

    Returns:
        str: The name with the "(Forts.)" suffix removed, if it was present.

    Examples:
        >>> normalize_name("John (Forts.)")
        "John"
        >>> normalize_name("John")
        "John"

    Notes:
        - The function assumes that "(Forts.)" occurs only as a suffix in the name.
        - This function is case-sensitive.
    """

    # Remove "(Forts.)" suffix from the name by splitting on it and taking the first part
    return name.split(' (Forts.)')[0]


def process_multiple_persons_text(text):
    """
    Process a block of text to extract information about multiple persons and their shifts.

    Parameters:
        text (str): The block of text containing information about multiple persons and their shifts.

    Returns:
        dict: A dictionary where each key is a normalized name and the value is a list of shift data for that person.

    Example:
        Input text:
        "Doe, John\nShift 1\nShift 2\nDoe, Jane (Forts.)\nShift 3"
        Output:
        {"Doe, John": ["Shift 1", "Shift 2"], "Doe, Jane": ["Shift 3"]}
    """

    def clean_name(name):
        """Clean up the name by removing extra white spaces and standardizing the format."""
        name = name.strip()
        name = re.sub(r'\s+', ' ', name)  # Remove extra white spaces
        return re.sub(r'\s*,\s*', ', ', name)  # Ensure single space after comma

    lines = text.strip().split("\n")
    persons_data = {}
    current_name = None
    shift_data = []  # This list will store the shift data associated with a name

    for line in lines:
        # Regular expression pattern to match names
        name_match = re.search(r'^([a-zA-ZäöüÄÖÜß\s]+,\s*[a-zA-ZäöüÄÖÜß\s]+)', line)

        if name_match:
            if current_name:
                # Process the shift information for the previous person
                processed_shifts = process_extracted_text("\n".join(shift_data))
                if processed_shifts:
                    persons_data[current_name].extend(processed_shifts)
                shift_data = []  # Clear shift data before moving on to the next person

            # Clean and normalize the name
            raw_name = clean_name(name_match.group(1))
            current_name = normalize_name(raw_name)

            # Initialize the list for the current name if it's not already present
            if current_name not in persons_data:
                persons_data[current_name] = []

        elif current_name:
            # Gather the shift data for the current name
            shift_data.append(line)

    if current_name and shift_data:
        # Don't forget to process the shifts for the last person in the text
        processed_shifts = process_extracted_text("\n".join(shift_data))
        if processed_shifts:
            persons_data[current_name].extend(processed_shifts)

    return persons_data


def create_shift_statistics(persons_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, int]]:
    """
    Generate statistics on shifts for each person in the provided data.

    Parameters:
    - persons_data (Dict[str, List[Dict[str, Any]]]): Dictionary where keys are names
      and values are lists of dictionaries containing shift data.

    Returns:
    - all_stats (Dict[str, Dict[str, int]]): Dictionary where keys are names and values are
      dictionaries containing shift statistics for each unique shift entry.
    """
    all_stats = {}  # Initialize a dictionary to hold the shift statistics for each person

    for person, shifts in persons_data.items():
        # Use Counter to collect statistics for the current person efficiently
        stats = Counter(shift["entry"] for shift in shifts)

        # Convert the Counter to a regular dictionary and store it in all_stats
        all_stats[person] = dict(stats)

    return all_stats


def process_full_text(text: str) -> Tuple[Optional[str], Optional[List[Dict[str, str]]]]:
    """
    Process the provided text to extract both the person's name and their shifts.

    Parameters:
    - text (str): The raw text containing both the person's name and shifts.

    Returns:
    - Tuple[Optional[str], Optional[List[Dict[str, str]]]]: A tuple containing the name of the person
      and a list of dictionaries containing shift information. Both could be None if the input is invalid.
    """
    # Split the text into lines and strip any leading/trailing whitespace
    lines = [line.strip() for line in text.strip().split("\n")]

    # Validate that the text contains enough lines for processing
    if len(lines) < 4:
        return None, None

    # Extract and validate the person's name from the third line
    name = lines[2]
    if not name:
        return None, None

    # Extract the text for shifts, starting from the fourth line
    shifts_text = "\n".join(lines[3:])

    # Use an existing function to process the shifts
    shifts = process_extracted_text(shifts_text)

    # Validate that the shifts are non-empty
    if not shifts:
        return name, None

    return name, shifts


def allowed_file(filename: str) -> bool:
    """
    Check if the uploaded file has an allowed extension.

    Parameters:
    - filename (str): The name of the file being uploaded.

    Returns:
    - bool: True if the file has an allowed extension, False otherwise.
    """
    # Validate that the filename is not empty
    if not filename:
        return False

    # Ensure the filename contains a period, indicating an extension
    if '.' not in filename:
        return False

    # Extract and normalize the file extension from the filename
    file_extension = filename.rsplit('.', 1)[1].strip().lower()

    # Validate that the extracted extension is not empty
    if not file_extension:
        return False

    # Check if the extracted extension is among the list of allowed extensions
    return file_extension in current_app.config['ALLOWED_EXTENSIONS']


def common_slugify(text: str) -> Optional[str]:
    try:
        if not text:
            raise ValueError("The text parameter cannot be empty or None.")

        slugified_text = slugify(
            text,
            replacements=[('ü', 'ue'), ('ö', 'oe'), ('ä', 'ae'), ('ß', 'ss')],
            lowercase=True
        )

        if not slugified_text:
            raise ValueError("Failed to create a slugified text.")

        return slugified_text

    except Exception as e:
        logging.error(f"An error occurred while slugifying the text: {e}")
        raise


def create_slugified_filename(name: str) -> Optional[str]:
    return common_slugify(name)


def extract_name_from_text(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.strip().split("\n")]
    if len(lines) < 3:
        return None
    name_line = lines[2]
    return common_slugify(name_line)

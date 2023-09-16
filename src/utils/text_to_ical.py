from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz


def convert_shifts_to_ical(shifts):
    """Converts a list of shift dictionaries to an iCal formatted calendar string.

    Parameters:
        shifts (list): A list of shift dictionaries with details.

    Returns:
        str: The iCal formatted calendar string.
    """
    # Initialize a new calendar
    cal = Calendar()

    # Define the timezone to be used
    tz = pytz.timezone('Europe/Vienna')

    def create_event(shift):
        """Creates an Event instance based on a single shift dictionary."""
        e = Event()

        try:
            start_date = datetime.strptime(shift["date"], "%a. %d.%m.%Y")

            if shift["all_day"]:
                e.name = shift["entry"]
                e.begin = tz.localize(start_date)
                e.make_all_day()
            else:
                start_time_str, end_time_str = shift["shift_time"].split("-")
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()

                start_datetime = tz.localize(datetime.combine(start_date, start_time))
                end_datetime = tz.localize(datetime.combine(start_date, end_time))

                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)

                e.name = shift["entry"]
                e.begin = start_datetime
                e.end = end_datetime

            return e
        except (ValueError, KeyError) as ex:
            print(f"Error occurred while creating an event: {ex}")
            return None

    # Process each shift list and each shift within it
    for shift_list in shifts:
        for shift in shift_list:
            event = create_event(shift)
            if event:
                cal.events.add(event)

    return cal.serialize()

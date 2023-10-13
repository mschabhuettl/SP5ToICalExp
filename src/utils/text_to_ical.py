from ics import Calendar, Event
from datetime import datetime, timedelta
from dateutil import tz

def convert_shifts_to_ical(shifts, timezone='Europe/Vienna'):
    """
    Converts a list of shift dictionaries into an iCal formatted calendar string.

    Parameters:
        shifts (list): A list of shift dictionaries with details.
        timezone (str): The string representation of the timezone. Default is 'Europe/Vienna'.

    Returns:
        str: The iCal formatted calendar string.
    """
    cal = Calendar()

    tz_info = tz.gettz(timezone)
    if not tz_info:
        print(f"Invalid timezone: {timezone}")
        return None

    def create_event(shift):
        """Creates an Event instance based on a single shift dictionary."""
        e = Event()

        try:
            start_date = datetime.strptime(shift["date"], "%a. %d.%m.%Y")

            if shift.get("all_day", False):
                e.name = shift["entry"]
                e.begin = start_date.replace(tzinfo=tz_info)
                e.make_all_day()
            else:
                start_time_str, end_time_str = shift["shift_time"].split("-")
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()

                start_datetime = datetime.combine(start_date, start_time).replace(tzinfo=tz_info)
                end_datetime = datetime.combine(start_date, end_time).replace(tzinfo=tz_info)

                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)

                e.name = shift["entry"]
                e.begin = start_datetime
                e.end = end_datetime

            return e
        except (ValueError, KeyError) as ex:
            print(f"Error occurred while creating an event: {ex}. Shift: {shift}")
            return None

    for shift_list in shifts:
        for shift in shift_list:
            event = create_event(shift)
            if event:
                cal.events.add(event)

    return cal.serialize()

from calendar import monthrange
from datetime import date


def get_month_start_and_end(year, month):
    """
    Return the first and last date of a month.
    """
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])

    return start, end


def get_safe_month_date(year, month, day):
    """
    Return a valid date for the month, using the last day when needed.
    """
    last_day = monthrange(year, month)[1]
    safe_day = min(day, last_day)

    return date(year, month, safe_day)
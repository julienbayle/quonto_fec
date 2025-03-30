import pytz
from datetime import datetime


def conv_date_from_utc_to_local(date: str | datetime) -> datetime:
    """
    Normalize a date to Europe/Paris timezone from a UTC based date
    """
    if type(date) is str:
        try:
            date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            try:
                date = datetime.strptime(str(date), "%Y-%m-%d")
            except ValueError:
                date = datetime.strptime(str(date), "%Y%m%d")

    local_tz = pytz.timezone("Europe/Paris")
    utc_tz = pytz.timezone("UTC")
    dt_utc = utc_tz.localize(date)
    dt_local = local_tz.normalize(dt_utc)
    if type(dt_local) is datetime:
        return dt_local
    else:
        raise ValueError("Technical error - Date is not a datime after conversion")

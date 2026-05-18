import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta

CALENDAR_ID = "prokhorov.on@gmail.com"

def get_calendar_service():
    key_json = os.environ.get("GOOGLE_KEY")
    if key_json:
        info = json.loads(key_json)
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
    else:
        with open("calendar_key.json") as f:
            info = json.load(f)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)

def add_event(title, assignee, deadline, time_str=None, time_end=None):
    if not assignee:
        assignee = "-"
    if not deadline:
        return None
    try:
        service = get_calendar_service()
        if time_str and time_str != "null":
            start = deadline + "T" + time_str + ":00"
            if time_end and time_end != "null":
                end = deadline + "T" + time_end + ":00"
            else:
                end_dt = datetime.fromisoformat(start) + timedelta(hours=1)
                end = end_dt.isoformat()
            event = {
                "summary": title + " (" + assignee + ")",
                "description": "Vidpovidalnyj: " + assignee,
                "start": {"dateTime": start, "timeZone": "Europe/Madrid"},
                "end": {"dateTime": end, "timeZone": "Europe/Madrid"},
            }
        else:
            event = {
                "summary": title + " (" + assignee + ")",
                "description": "Vidpovidalnyj: " + assignee,
                "start": {"date": deadline},
                "end": {"date": deadline},
            }
        result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return result.get("htmlLink")
    except Exception as e:
        print("Calendar error:", e)
        return None

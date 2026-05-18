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

def get_team_emails():
    raw = os.environ.get("TEAM_EMAILS", "")
    result = {}
    for pair in raw.split(","):
        if ":" in pair:
            name, email = pair.strip().split(":", 1)
            result[name.strip().lower()] = email.strip()
    return result

def find_email(assignee):
    if not assignee:
        return None
    emails = get_team_emails()
    assignee_lower = assignee.lower()
    for name, email in emails.items():
        if name in assignee_lower or assignee_lower in name:
            return email
    return None

def add_event(title, assignee, deadline, time_str=None, time_end=None):
    if not assignee:
        assignee = "-"
    if not deadline:
        return None
    try:
        service = get_calendar_service()

        # Шукаємо email відповідального
        attendees = []
        email = find_email(assignee)
        if email:
            attendees.append({"email": email})

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
                "attendees": attendees,
                "sendUpdates": "all",
            }
        else:
            event = {
                "summary": title + " (" + assignee + ")",
                "description": "Vidpovidalnyj: " + assignee,
                "start": {"date": deadline},
                "end": {"date": deadline},
                "attendees": attendees,
                "sendUpdates": "all",
            }
        result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return result.get("htmlLink")
    except Exception as e:
        print("Calendar error:", e)
        return None

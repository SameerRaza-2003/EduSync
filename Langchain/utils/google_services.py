# utils/google_services.py
from googleapiclient.discovery import build

def get_service(creds):
    gcr = build("classroom", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    return gcr, calendar_service

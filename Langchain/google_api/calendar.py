# google_api/calendar.py
# Make sure this file exists in a 'google_api' subfolder or adjust imports
import datetime

def create_calendar_events(pending_assignments, service):
    if not service:
        raise ValueError("Calendar service object is None in create_calendar_events")
    if not pending_assignments or not isinstance(pending_assignments, dict):
        print("Warning: create_calendar_events called with invalid or empty pending_assignments.")
        return # Or raise an error, or return a status

    event_creation_summary = []
    
    for course, data in pending_assignments.items():
        for assignment in data.get("not_submitted", []):
            title = assignment.get("title", "Untitled Assignment")
            date_str = assignment.get("due_date")
            time_str = assignment.get("due_time")

            if not date_str or date_str == "N/A": # Skip if no valid date
                event_creation_summary.append(f"Skipped '{title}' for course '{course}' due to missing date.")
                continue

            try:
                # Ensure time_str is valid, default if needed
                if not time_str or time_str == "N/A" or ':' not in time_str:
                    time_str = "23:59" # Default to end of day if time is missing/invalid
                
                due_datetime_str = f"{date_str} {time_str}"
                due_datetime = datetime.datetime.strptime(due_datetime_str, "%Y-%m-%d %H:%M")
            except ValueError as e:
                # Fallback if time parsing fails, use a default time like noon
                try:
                    due_datetime = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    due_datetime = due_datetime.replace(hour=12, minute=0) # Default to noon
                    event_creation_summary.append(f"Warning: Used default time for '{title}' due to parsing error: {e}")
                except ValueError:
                    event_creation_summary.append(f"Skipped '{title}' for course '{course}' due to invalid date format: {date_str}")
                    continue


            event = {
                "summary": f"[{course}] {title}",
                "description": "Google Classroom Assignment (Pending)",
                "start": {
                    "dateTime": due_datetime.isoformat(),
                    "timeZone": "Asia/Karachi", # Make this configurable or get from user's calendar if possible
                },
                "end": {
                    "dateTime": (due_datetime + datetime.timedelta(hours=1)).isoformat(),
                    "timeZone": "Asia/Karachi", # Make this configurable
                },
            }
            try:
                service.events().insert(calendarId="primary", body=event).execute()
                event_creation_summary.append(f"Successfully added '{title}' for course '{course}' to calendar.")
            except Exception as e:
                event_creation_summary.append(f"Failed to add '{title}' for course '{course}' to calendar: {e}")
    
    print("\n".join(event_creation_summary)) # For server-side logging
    # Return a summary string or a more structured status
    return "Calendar event creation process finished. Check logs for details. " + " ".join(event_creation_summary[:3]) # Brief summary
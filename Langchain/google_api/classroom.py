# google_api/classroom.py

def get_coursework_with_submissions(service):
    """
    Fetches all Google Classroom assignments and returns a human-readable string summary.
    """
    if not service:
        raise ValueError("Classroom service object is None in get_coursework_with_submissions")

    results = service.courses().list(pageSize=20).execute()
    courses = results.get("courses", [])
    coursework_summary_parts = []

    if not courses:
        return "No courses found in your Google Classroom."

    for course in courses:
        course_id = course["id"]
        course_name = course["name"]

        coursework_result = service.courses().courseWork().list(courseId=course_id).execute()
        coursework_items = coursework_result.get("courseWork", [])

        if not coursework_items:
            continue

        submitted_for_course = []
        not_submitted_for_course = []

        for work in coursework_items:
            work_id = work["id"]
            title = work.get("title", "No Title")
            due_date_obj = work.get("dueDate", {})
            due_time_obj = work.get("dueTime", {})

            date_str = "N/A"
            if due_date_obj and due_date_obj.get('year') and due_date_obj.get('month') and due_date_obj.get('day'):
                date_str = f"{due_date_obj.get('year')}-{due_date_obj.get('month', 0):02d}-{due_date_obj.get('day', 0):02d}"

            time_str = "N/A"
            if due_time_obj and due_time_obj.get('hours') is not None:
                 time_str = f"{due_time_obj.get('hours', 0):02d}:{due_time_obj.get('minutes', 0):02d}"

            submission_result = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=work_id,
                userId="me"
            ).execute()
            submissions = submission_result.get("studentSubmissions", [])
            
            current_status = "Status: NOT_SUBMITTED (or no submission object)"
            is_submitted_flag = False

            if submissions and isinstance(submissions, list) and len(submissions) > 0 and isinstance(submissions[0], dict):
                sub_state = submissions[0].get("state")
                if sub_state:
                    current_status = f"Status: {sub_state}"
                    if sub_state in {"TURNED_IN", "RETURNED"}:
                        is_submitted_flag = True
            
            assignment_details = f"- {title} | Due: {date_str} at {time_str} | {current_status}"
            if is_submitted_flag:
                submitted_for_course.append(assignment_details)
            else:
                not_submitted_for_course.append(assignment_details)

        if submitted_for_course or not_submitted_for_course:
            course_summary = f"\n📘 **{course_name}**\n"
            if submitted_for_course:
                course_summary += "\n✅ Submitted Assignments:\n" + "\n".join(submitted_for_course)
            if not_submitted_for_course:
                course_summary += "\n❌ Not Submitted Assignments:\n" + "\n".join(not_submitted_for_course)
            coursework_summary_parts.append(course_summary)

    if not coursework_summary_parts:
        return "No assignments found with details in your Google Classroom courses."

    return "\n\n".join(coursework_summary_parts)


def get_pending_assignments_for_calendar(service):
    """
    Fetches Google Classroom assignments that are not submitted and have due dates,
    returning them as structured data suitable for adding to a calendar.
    Output: {"Course Name": {"not_submitted": [{"title": ..., "due_date": ..., "due_time": ...}]}}
            or an empty dict {} if no such assignments or an error.
    """
    if not service:
        raise ValueError("Classroom service object is None in get_pending_assignments_for_calendar")
    
    results = service.courses().list(pageSize=20).execute()
    courses = results.get("courses", [])
    pending_assignments_data = {}

    if not courses:
        return {}

    for course in courses:
        course_id = course["id"]
        course_name = course["name"]

        coursework_result = service.courses().courseWork().list(courseId=course_id).execute()
        coursework_items = coursework_result.get("courseWork", [])

        if not coursework_items:
            continue

        course_not_submitted_list = []

        for work in coursework_items:
            work_id = work["id"]
            title = work.get("title", "No Title")
            due_date_obj = work.get("dueDate", {})
            due_time_obj = work.get("dueTime", {})

            year = due_date_obj.get('year')
            month = due_date_obj.get('month')
            day = due_date_obj.get('day')

            if not all([year, month, day]):
                continue 
            date_str = f"{year}-{month:02d}-{day:02d}"
            
            hours = due_time_obj.get('hours', 23) 
            minutes = due_time_obj.get('minutes', 59)
            time_str = f"{hours:02d}:{minutes:02d}"

            submission_result = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=work_id,
                userId="me"
            ).execute()
            submissions = submission_result.get("studentSubmissions", [])
            
            is_submitted = False
            if submissions and isinstance(submissions, list) and len(submissions) > 0 and isinstance(submissions[0], dict):
                sub_state = submissions[0].get("state")
                if sub_state and sub_state in {"TURNED_IN", "RETURNED"}:
                    is_submitted = True
            
            if not is_submitted:
                course_not_submitted_list.append({
                    "title": title,
                    "due_date": date_str,
                    "due_time": time_str
                })

        if course_not_submitted_list:
            pending_assignments_data[course_name] = {"not_submitted": course_not_submitted_list}
            
    return pending_assignments_data
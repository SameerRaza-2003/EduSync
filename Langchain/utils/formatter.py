def format_context(coursework_dict):
    context = ""
    for course, details in coursework_dict.items():
        context += f"\nCourse: {course}\n"
        context += "Submitted Assignments:\n"
        if not details["submitted"]:
            context += "_No submitted assignments._\n"
        else:
            for a in details["submitted"]:
                context += f"- {a['title']} (Due: {a['due_date']} at {a['due_time']})\n"
        context += "Not Submitted Assignments:\n"
        if not details["not_submitted"]:
            context += "_No unsubmitted assignments._\n"
        else:
            for a in details["not_submitted"]:
                context += f"- {a['title']} (Due: {a['due_date']} at {a['due_time']})\n"
    return context

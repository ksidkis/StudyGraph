from services.schedule_service import (
    create_schedule_for_user,
    fetch_user_schedule,
)

def run_agent(user_email, action, data=None):
    if action == "create_schedule":
        return create_schedule_for_user(user_email, data)

    elif action == "get_schedule":
        return fetch_user_schedule(user_email)

    else:
        return {"error": "Unknown action"}
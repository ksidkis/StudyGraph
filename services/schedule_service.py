from database.db_helper import (
    get_user_by_email,
    insert_study_schedule,
    get_schedule_for_user,
)

def create_schedule_for_user(email, schedule_data):
    user = get_user_by_email(email)

    if not user:
        raise Exception("User not found")

    insert_study_schedule(user["id"], schedule_data)

    return {"status": "created"}


def fetch_user_schedule(email):
    user = get_user_by_email(email)

    if not user:
        raise Exception("User not found")

    return get_schedule_for_user(user["id"])
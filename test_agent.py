from database.db_helper import upsert_user

user = upsert_user(
    email="test@example.com",
    access_token="dummy",
    refresh_token="dummy",
    token_expiry=None
)

print(user)
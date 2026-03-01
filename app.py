"""Main Streamlit app that orchestrates OAuth, LangGraph generation, scheduling, DB writes, and Calendar sync."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

from agent.graph import run_study_graph
from database.db_helper import (
    clear_schedule_for_user,
    get_schedule_for_user,
    upsert_user,
    insert_study_schedule,
)
from services.calendar_service import push_schedule_to_calendar
from services.scheduler import build_schedule


load_dotenv()

st.set_page_config(page_title="StudyGraph", layout="wide")
st.title("StudyGraph: Autonomous Learning Planner")


def _parse_scopes() -> list[str]:
    scopes = os.getenv("GOOGLE_CALENDAR_SCOPES", "https://www.googleapis.com/auth/calendar")
    return [s.strip() for s in scopes.split(",") if s.strip()]


def _build_oauth_flow() -> Flow:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

    if not client_id or not client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required in .env")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            }
        },
        scopes=_parse_scopes(),
    )
    flow.redirect_uri = redirect_uri
    return flow


def _infer_start_date(goal: str) -> datetime.date:
    # Uses current local date by default; explicit date parsing can be added if needed.
    return datetime.now().date()


if "tokens" not in st.session_state:
    st.session_state.tokens = None

with st.container(border=True):
    st.subheader("1) Connect Google Calendar")
    email = st.text_input("Email", placeholder="you@example.com")

    flow = _build_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    st.markdown(f"Authorize here: [Google OAuth Consent]({auth_url})")
    auth_code = st.text_input("Paste authorization code")

    if st.button("Exchange Code for Tokens", use_container_width=True):
        if not email or not auth_code:
            st.error("Email and authorization code are required.")
        else:
            try:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                st.session_state.tokens = {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "expiry": creds.expiry,
                    "email": email.strip().lower(),
                }
                st.success("Google tokens acquired and ready to save in PostgreSQL.")
            except Exception as exc:
                st.error(f"OAuth exchange failed: {exc}")

with st.container(border=True):
    st.subheader("2) Generate Plan with LangGraph")
    goal = st.text_area(
        "Study Goal",
        value="Teach me Oracle SQL in 14 days",
        help="Example: Teach me Oracle SQL in 14 days",
    )

    if st.button("Generate, Schedule, and Save", type="primary", use_container_width=True):
        if not st.session_state.tokens:
            st.error("Complete Google OAuth first.")
        elif not goal.strip():
            st.error("Study goal is required.")
        else:
            try:
                with st.spinner("Generating syllabus and 500-word module content via LangGraph..."):
                    modules = run_study_graph(goal.strip())

                with st.spinner("Saving user and schedule to PostgreSQL..."):
                    user = upsert_user(
                        email=st.session_state.tokens["email"],
                        access_token=st.session_state.tokens["access_token"],
                        refresh_token=st.session_state.tokens["refresh_token"],
                        token_expiry=st.session_state.tokens["expiry"],
                    )

                    scheduled_rows = build_schedule(modules, start_date=_infer_start_date(goal))
                    clear_schedule_for_user(user["id"])
                    insert_study_schedule(user["id"], scheduled_rows)

                st.success(f"Saved {len(scheduled_rows)} schedule rows for {user['email']}.")
            except Exception as exc:
                st.error(f"Plan generation or DB write failed: {exc}")

with st.container(border=True):
    st.subheader("3) Push to Google Calendar")
    if st.button("Push Unsynced Events", use_container_width=True):
        tokens = st.session_state.tokens
        if not tokens:
            st.error("Complete OAuth first.")
        else:
            try:
                created = push_schedule_to_calendar(tokens["email"])
                st.success(f"Created {created} new Google Calendar event(s).")
            except Exception as exc:
                st.error(f"Calendar sync failed: {exc}")

with st.container(border=True):
    st.subheader("4) Current Saved Schedule")
    tokens = st.session_state.tokens
    if tokens:
        try:
            user = upsert_user(
                email=tokens["email"],
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_expiry=tokens["expiry"],
            )
            rows = get_schedule_for_user(user["id"], only_unsynced=False)
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No saved schedule rows yet.")
        except Exception as exc:
            st.warning(f"Could not load schedule table: {exc}")
    else:
        st.info("Authenticate first to view your schedule.")
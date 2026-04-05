"""
sheets_logger.py
Logs each pipeline run to a Google Sheet.

Sheet columns (auto-created on first run):
  Timestamp | Status | Niche | Idea | Video URL | Error
"""

import os
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS = ["Timestamp", "Status", "Niche", "Idea", "Video URL", "Error"]


def _get_sheet():
    """Return the first sheet of the configured Google Spreadsheet, or None."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")

    if not creds_json or not sheet_id:
        return None

    creds = Credentials.from_service_account_info(
        json.loads(creds_json), scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def _ensure_headers(sheet) -> None:
    """Add header row if the sheet is empty."""
    if not sheet.row_values(1):
        sheet.append_row(HEADERS, value_input_option="RAW")


def log_run(results: dict) -> None:
    """
    Append one row to the Google Sheet summarising a pipeline run.
    Silently skips if Google Sheets is not configured.
    """
    try:
        sheet = _get_sheet()
        if sheet is None:
            print("Google Sheets not configured — skipping log.")
            return

        _ensure_headers(sheet)

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            results.get("status", "unknown"),
            results.get("niche", ""),
            results.get("idea", ""),
            results.get("video_url", ""),
            results.get("error", ""),
        ]
        sheet.append_row(row, value_input_option="RAW")
        print("Logged to Google Sheets ✓")

    except Exception as exc:
        # Never let a logging failure break the main flow
        print(f"Google Sheets log error (non-fatal): {exc}")

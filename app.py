import os
import json
from datetime import date

import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

BRANCHES = [
    "MANJERI", "KASARGOD", "KANNUR", "KUTTYADI", "KOZHIKODE", "TIRUR",
    "PALAKKAD", "THRISSUR", "ALAPPUZHA", "KOLLAM", "TRIVANDRUM",
    "MARTHANDAM", "NAGPUR", "HYDERABAD", "BANGALORE"
]

FIELDS = ["dial", "plan", "live_int", "reg_visit", "reg_from_rm"]

SHEET_TAB_NAME = "Sheet1"

# Fixed layout on the sheet (row 3 = headers, data starts row 4):
# A: SL NO | B: BRANCH | C: RMs NAME | D: JOINING DATE | E: DATE
# F: NO. OF WORKING DAYS | G: DIAL | H: PLAN | I: LIVE INT | J: REG VISIT | K: REG
HEADER_ROW = 3
FIRST_DATA_ROW = 4
COL_SL_NO = 1
COL_BRANCH = 2
COL_RM = 3
COL_JOINING_DATE = 4
COL_DATE = 5
COL_WORKING_DAYS = 6
COL_DIAL = 7
COL_PLAN = 8
COL_LIVE_INT = 9
COL_REG_VISIT = 10
COL_REG = 11

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None
_worksheet = None


def get_worksheet():
    """Authenticates with Google and returns the target worksheet (tab).

    Env vars required:
      GOOGLE_CREDENTIALS_JSON - full contents of the service account JSON key
      SPREADSHEET_ID          - the id from the sheet's URL
    """
    global _client, _worksheet
    if _worksheet is not None:
        return _worksheet

    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    spreadsheet_id = os.environ["SPREADSHEET_ID"]

    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    _client = gspread.authorize(creds)
    spreadsheet = _client.open_by_key(spreadsheet_id)
    _worksheet = spreadsheet.worksheet(SHEET_TAB_NAME)
    return _worksheet


def find_row(ws, branch, rm):
    """Returns the 1-indexed row number for this branch+RM, or None."""
    values = ws.get_all_values()
    for i in range(FIRST_DATA_ROW - 1, len(values)):
        row = values[i]
        row_branch = row[COL_BRANCH - 1] if len(row) >= COL_BRANCH else ""
        row_rm = row[COL_RM - 1] if len(row) >= COL_RM else ""
        if row_branch.strip() == branch and row_rm.strip() == rm:
            return i + 1  # sheet rows are 1-indexed
    return None


def first_empty_row(ws):
    values = ws.get_all_values()
    for i in range(FIRST_DATA_ROW - 1, len(values)):
        row = values[i]
        row_branch = row[COL_BRANCH - 1] if len(row) >= COL_BRANCH else ""
        row_rm = row[COL_RM - 1] if len(row) >= COL_RM else ""
        if not row_branch.strip() and not row_rm.strip():
            return i + 1
    return len(values) + 1  # append past the end if the template is full


def ensure_row(ws, branch, rm):
    """Finds this branch+RM's row, or creates it in the next empty slot."""
    row_num = find_row(ws, branch, rm)
    if row_num:
        return row_num

    row_num = first_empty_row(ws)
    sl_no = row_num - FIRST_DATA_ROW + 1
    today = date.today().strftime("%d/%m/%Y")
    ws.update(
        f"A{row_num}:D{row_num}",
        [[sl_no, branch, rm, today]],
    )
    return row_num


@app.route("/")
def index():
    return render_template("index.html", branches=BRANCHES)


@app.route("/api/branches")
def api_branches():
    return jsonify(BRANCHES)


@app.route("/api/rms")
def api_rms():
    branch = request.args.get("branch", "")
    ws = get_worksheet()
    values = ws.get_all_values()
    names = []
    for row in values[FIRST_DATA_ROW - 1:]:
        row_branch = row[COL_BRANCH - 1] if len(row) >= COL_BRANCH else ""
        row_rm = row[COL_RM - 1] if len(row) >= COL_RM else ""
        if row_branch.strip() == branch and row_rm.strip():
            names.append(row_rm.strip())
    return jsonify(names)


@app.route("/api/rms", methods=["POST"])
def add_rm():
    data = request.get_json(force=True)
    branch = (data.get("branch") or "").strip()
    name = (data.get("name") or "").strip()
    if not branch or not name:
        return jsonify({"error": "branch and name are required"}), 400

    ws = get_worksheet()
    ensure_row(ws, branch, name)
    return jsonify({"ok": True})


@app.route("/api/reports", methods=["POST"])
def add_report():
    data = request.get_json(force=True)
    branch = (data.get("branch") or "").strip()
    rm = (data.get("rm") or "").strip()
    if not branch or not rm:
        return jsonify({"error": "branch and rm are required"}), 400

    values = {f: int(data.get(f) or 0) for f in FIELDS}

    ws = get_worksheet()
    row_num = ensure_row(ws, branch, rm)
    today = date.today().strftime("%d/%m/%Y")

    ws.update(f"E{row_num}", [[today]])
    ws.update(
        f"G{row_num}:K{row_num}",
        [[values["dial"], values["plan"], values["live_int"], values["reg_visit"], values["reg_from_rm"]]],
    )
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
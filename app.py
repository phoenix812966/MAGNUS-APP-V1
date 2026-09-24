import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

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
RM_TAB_NAME = "RM Details"

# RM Details tab layout (row 1 = headers, data from row 2):
# A: SL NO | B: BRANCH | C: RM NAME | D: ADDED ON | E: LAST SUBMITTED
RM_HEADERS = ["SL NO", "BRANCH", "RM NAME", "ADDED ON", "LAST SUBMITTED"]
RM_COL_LAST_SUBMITTED = 5
IST = ZoneInfo("Asia/Kolkata")


def today_str():
    return datetime.now(IST).strftime("%Y-%m-%d")
RM_FIRST_DATA_ROW = 2

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
_rm_worksheet = None
_spreadsheet = None


def get_worksheet():
    """Authenticates with Google and returns the target worksheet (tab).

    Env vars required:
      GOOGLE_CREDENTIALS_JSON - full contents of the service account JSON key
      SPREADSHEET_ID          - the id from the sheet's URL
    """
    global _client, _worksheet, _spreadsheet
    if _worksheet is not None:
        return _worksheet

    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    spreadsheet_id = os.environ["SPREADSHEET_ID"]

    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    _client = gspread.authorize(creds)
    _spreadsheet = _client.open_by_key(spreadsheet_id)
    _worksheet = _spreadsheet.worksheet(SHEET_TAB_NAME)
    return _worksheet


def get_rm_worksheet():
    """Returns the "RM Details" tab, creating it (with headers) if missing.

    On first use it also copies any RMs that already exist on Sheet1 into
    RM Details, so nothing added before this change is lost.
    """
    global _rm_worksheet
    if _rm_worksheet is not None:
        return _rm_worksheet

    ws = get_worksheet()  # also initialises _spreadsheet
    rm_ws = None
    for w in _spreadsheet.worksheets():
        if w.title.strip().lower() == RM_TAB_NAME.lower():
            rm_ws = w
            break
    if rm_ws is None:
        rm_ws = _spreadsheet.add_worksheet(title=RM_TAB_NAME, rows=200, cols=len(RM_HEADERS))
        rm_ws.update("A1:E1", [RM_HEADERS])
        rm_ws.format("A1:E1", {"textFormat": {"bold": True}})
    else:
        # older tab without the LAST SUBMITTED column: add its header
        header = rm_ws.row_values(1)
        if len(header) < RM_COL_LAST_SUBMITTED or not header[RM_COL_LAST_SUBMITTED - 1].strip():
            if rm_ws.col_count < RM_COL_LAST_SUBMITTED:
                rm_ws.add_cols(RM_COL_LAST_SUBMITTED - rm_ws.col_count)
            rm_ws.update_cell(1, RM_COL_LAST_SUBMITTED, RM_HEADERS[-1])

    _rm_worksheet = rm_ws
    _backfill_rm_details(ws, rm_ws)
    return _rm_worksheet


def _backfill_rm_details(ws, rm_ws):
    """One-time: copy branch+RM pairs already on Sheet1 into RM Details."""
    existing = {
        (r[1].strip().upper(), r[2].strip().upper())
        for r in rm_ws.get_all_values()[RM_FIRST_DATA_ROW - 1:]
        if len(r) >= 3
    }
    new_rows = []
    for row in ws.get_all_values()[FIRST_DATA_ROW - 1:]:
        b = row[COL_BRANCH - 1].strip() if len(row) >= COL_BRANCH else ""
        n = row[COL_RM - 1].strip() if len(row) >= COL_RM else ""
        if b and n and (b.upper(), n.upper()) not in existing:
            existing.add((b.upper(), n.upper()))
            new_rows.append([b, n])
    if new_rows:
        _append_rm_rows(rm_ws, new_rows)


def _append_rm_rows(rm_ws, pairs):
    """Appends [branch, name] pairs to RM Details with SL NO and timestamp."""
    start = len(rm_ws.get_all_values()) + 1
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = [
        [start + i - RM_FIRST_DATA_ROW + 1, b, n, stamp]
        for i, (b, n) in enumerate(pairs)
    ]
    rm_ws.update(f"A{start}:D{start + len(rows) - 1}", rows)


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
    ws.update(
        f"A{row_num}:C{row_num}",
        [[sl_no, branch, rm]],
    )
    return row_num


def init_sheets():
    """Runs at startup so the RM Details tab exists right away."""
    try:
        get_rm_worksheet()
        print("RM Details tab ready.", flush=True)
    except Exception as e:
        print(f"RM Details setup FAILED: {type(e).__name__}: {e}", flush=True)


init_sheets()


@app.route("/api/setup-check")
def setup_check():
    """Open this URL in the browser to see if the sheet setup works."""
    try:
        rm_ws = get_rm_worksheet()
        return jsonify({"ok": True, "tab": rm_ws.title})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/")
def index():
    return render_template("index.html", branches=BRANCHES)


@app.route("/api/branches")
def api_branches():
    return jsonify(BRANCHES)


@app.route("/api/rms")
def api_rms():
    """Returns RM names for the selected branch only, from the RM Details tab."""
    branch = request.args.get("branch", "").strip()
    if not branch:
        return jsonify([])
    rm_ws = get_rm_worksheet()
    names = []
    seen = set()
    for row in rm_ws.get_all_values()[RM_FIRST_DATA_ROW - 1:]:
        row_branch = row[1].strip() if len(row) >= 2 else ""
        row_rm = row[2].strip() if len(row) >= 3 else ""
        if row_branch.upper() == branch.upper() and row_rm and row_rm.upper() not in seen:
            seen.add(row_rm.upper())
            names.append(row_rm)
    return jsonify(names)


def branch_rm_rows(branch):
    """[(sheet_row_number, rm_name, last_submitted)] for this branch, de-duplicated."""
    rm_ws = get_rm_worksheet()
    out, seen = [], set()
    for i, row in enumerate(rm_ws.get_all_values()[RM_FIRST_DATA_ROW - 1:], start=RM_FIRST_DATA_ROW):
        b = row[1].strip() if len(row) >= 2 else ""
        n = row[2].strip() if len(row) >= 3 else ""
        last = row[RM_COL_LAST_SUBMITTED - 1].strip() if len(row) >= RM_COL_LAST_SUBMITTED else ""
        if b.upper() == branch.upper() and n and n.upper() not in seen:
            seen.add(n.upper())
            out.append((i, n, last))
    return out


@app.route("/api/status")
def api_status():
    """Today's submitted / not-submitted count for one branch."""
    branch = request.args.get("branch", "").strip()
    if not branch:
        return jsonify({"error": "branch is required"}), 400
    today = today_str()
    rows = branch_rm_rows(branch)
    submitted = [n for _, n, last in rows if last == today]
    pending = [n for _, n, last in rows if last != today]
    return jsonify({
        "total": len(rows),
        "submitted": len(submitted),
        "not_submitted": len(pending),
        "pending_names": pending,
    })


@app.route("/api/reports", methods=["GET"])
def get_report():
    branch = request.args.get("branch", "").strip()
    rm = request.args.get("rm", "").strip()
    if not branch or not rm:
        return jsonify({"error": "branch and rm are required"}), 400

    ws = get_worksheet()
    row_num = find_row(ws, branch, rm)
    if not row_num:
        # no existing row yet — return zeros
        return jsonify({f: 0 for f in FIELDS})

    row = ws.row_values(row_num)

    def cell(col_num):
        return row[col_num - 1] if len(row) >= col_num else ""

    def to_int(v):
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    return jsonify({
        "dial": to_int(cell(COL_DIAL)),
        "plan": to_int(cell(COL_PLAN)),
        "live_int": to_int(cell(COL_LIVE_INT)),
        "reg_visit": to_int(cell(COL_REG_VISIT)),
        "reg_from_rm": to_int(cell(COL_REG)),
    })


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

    ws.update(
        f"G{row_num}:K{row_num}",
        [[values["dial"], values["plan"], values["live_int"], values["reg_visit"], values["reg_from_rm"]]],
    )

    # mark this RM as submitted today (RM Details, LAST SUBMITTED column)
    rm_ws = get_rm_worksheet()
    for sheet_row, name, _ in branch_rm_rows(branch):
        if name.upper() == rm.upper():
            rm_ws.update_cell(sheet_row, RM_COL_LAST_SUBMITTED, today_str())
            break
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
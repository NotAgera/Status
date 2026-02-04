import os
import urllib.parse
from datetime import datetime, timedelta

import requests
import streamlit as st
import matplotlib.pyplot as plt

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Machine Status Dashboard",
                   layout="wide",
                   initial_sidebar_state="collapsed")

DARK_BG = "#2f2f2f"

# -------------------- CSS --------------------
st.markdown(
    f"""
    <style>
      .stApp, .main, div.block-container {{
        background-color: {DARK_BG} !important;
      }}
      div.block-container {{
        padding-top: 10px;
        max-width: 1400px;
      }}

      .page-title {{
        text-align:center;
        color:#ffffff;
        font-weight:800;
        margin: 0 0 12px 0;
      }}

      .status-pill {{
        width: 460px;
        margin: 0 auto 18px auto;
        padding: 16px 12px;
        border-radius: 18px;
        text-align: center;
        font-weight: 800;
        font-size: 28px;
        color: #ffffff;
        border: 3px solid #000000;
      }}

      .pie-title {{
        text-align: left;
        color: #ffffff;
        font-weight: 800;
        font-size: 20px;
        margin: 0 0 6px 4px;
      }}
      .percent-row {{
        margin: 0 0 6px 4px;
      }}
      .percent-row span {{
        margin-right: 12px;
        font-weight: 800;
        font-size: 14px;
      }}

      .status-card {{
        display: block;
        width: 260px;
        height: 160px;
        border-radius: 18px;
        border: 3px solid #000000;
        color: #ffffff;
        text-align:center;
        font-weight: 800;
        font-size: 24px;
        line-height: 160px;
        text-decoration: none;
        user-select: none;
        transition: filter .08s ease-in-out, transform .08s ease-in-out;
      }}
      .status-card:hover {{ filter: brightness(1.06); transform: translateY(-1px); }}
      .status-card:active {{ transform: translateY(0); filter: brightness(0.98); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- KONSTANTER --------------------
LOG_FILE = "statuslog.txt"
STATUSES = ["Up time", "Minor issue", "Warning", "Alarm", "Urgent"]
COLORS = {
    "Up time": "#005A08",
    "Minor issue": "#97D801",
    "Warning": "#E7AA00",
    "Alarm": "#D62400",
    "Urgent": "#AA00B9",
}
OLD_TO_NEW = {
    "Idle": "Up time",
    "Ingen aktiv status": "Up time",
    "No issues": "Up time",
}
REFRESH_MS = 2000

# -------------------- LOGIN (enkel) --------------------
USERNAME = "Massterly"
PASSWORD = "km123"

def show_login():
    st.markdown("<h1 class='page-title'>🔒 Login</h1>", unsafe_allow_html=True)
    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == USERNAME and pw == PASSWORD:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Incorrect username or password")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login()
    st.stop()

# -------------------- STATE --------------------
if "current_status" not in st.session_state:
    st.session_state["current_status"] = "Up time"
if "status_start" not in st.session_state:
    st.session_state["status_start"] = datetime.now()

# -------------------- GIST HJELPERE (permanent lagring) --------------------
def gist_enabled():
    return "GITHUB_TOKEN" in st.secrets and "GIST_ID" in st.secrets

def _gist_headers():
    return {"Authorization": f'token {st.secrets["GITHUB_TOKEN"]}',
            "Accept": "application/vnd.github+json"}

def gist_filename():
    return st.secrets.get("GIST_FILENAME", "statuslog.txt")

def read_gist_text() -> str:
    """Les hele filen fra Gist. Returnerer tom streng om ikke finnes."""
    gid = st.secrets["GIST_ID"]
    r = requests.get(f"https://api.github.com/gists/{gid}", headers=_gist_headers(), timeout=15)
    r.raise_for_status()
    files = r.json().get("files", {})
    fn = gist_filename()
    if fn not in files:
        return ""
    raw_url = files[fn].get("raw_url")
    if not raw_url:
        return ""
    rr = requests.get(raw_url, timeout=15)
    rr.raise_for_status()
    return rr.text

def append_gist_line(line: str):
    """Append en linje til Gist-filen (les → legg til → patch)."""
    gid = st.secrets["GIST_ID"]
    fn = gist_filename()
    try:
        current = read_gist_text()
    except Exception as e:
        # nettfeil -> bare logg lokalt som fallback
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        return
    if current and not current.endswith("\n"):
        current += "\n"
    new_content = (current or "") + line + "\n"
    payload = {"files": {fn: {"content": new_content}}}
    r = requests.patch(f"https://api.github.com/gists/{gid}",
                       headers=_gist_headers(), json=payload, timeout=20)
    r.raise_for_status()

# -------------------- LOGG I/O (velg Gist hvis mulig) --------------------
def write_log(status, start, end):
    line = f"{status}, Start: {start.strftime('%Y-%m-%d %H:%M:%S')}, Slutt: {end.strftime('%Y-%m-%d %H:%M:%S')}"
    if gist_enabled():
        try:
            append_gist_line(line)
        except Exception as e:
            st.warning(f"Gist write failed, wrote locally instead: {e}")
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
    else:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

def read_log():
    if gist_enabled():
        try:
            text = read_gist_text()
        except Exception as e:
            st.warning(f"Gist read failed, using local: {e}")
            text = open(LOG_FILE, "r").read() if os.path.exists(LOG_FILE) else ""
    else:
        text = open(LOG_FILE, "r").read() if os.path.exists(LOG_FILE) else ""

    entries = []
    for line in text.splitlines():
        if "Start:" in line and "Slutt:" in line:
            try:
                statuspart, s_part, e_part = line.split(",")
                status = OLD_TO_NEW.get(statuspart.strip(), statuspart.strip())
                s = datetime.strptime(s_part.replace("Start:", "").strip(), "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(e_part.replace("Slutt:", "").strip(), "%Y-%m-%d %H:%M:%S")
                entries.append((status, s, e))
            except:
                pass
    return entries

def add_active(log):
    return log + [(st.session_state["current_status"],
                   st.session_state["status_start"],
                   datetime.now())]

# -------------------- SUMMERINGER --------------------
def sum_day(log):
    today = datetime.now().date()
    totals = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() == today:
            totals[status] += (e - s).seconds
    return totals

def sum_week(log):
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    totals = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() >= monday:
            totals[status] += (e - s).seconds
    return totals

def sum_month(log):
    now = datetime.now()
    mstart = datetime(now.year, now.month, 1).date()
    totals = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() >= mstart:
            totals[status] += (e - s).seconds
    return totals

# -------------------- STATUS-ENDRING --------------------
def change_status(new_status: str):
    # fullfør forrige
    write_log(st.session_state["current_status"],
              st.session_state["status_start"],
              datetime.now())
    # start ny
    st.session_state["current_status"] = new_status
    st.session_state["status_start"] = datetime.now()

# Query-param (knapper nederst er lenker)
qp = st.experimental_get_query_params()
if "set" in qp:
    new_val = qp["set"][0]
    if new_val in STATUSES:
        change_status(new_val)
    st.experimental_set_query_params()  # tøm etter bruk

# -------------------- TOPP: STATUS-PILL --------------------
curr = st.session_state["current_status"]
st.markdown(f"<div class='status-pill' style='background:{COLORS[curr]};'>{curr}</div>", unsafe_allow_html=True)

# -------------------- PIES --------------------
def draw_pie_block(title: str, totals: dict):
    st.markdown(f"<div class='pie-title'>{title}</div>", unsafe_allow_html=True)

    total_sum = sum(totals.values())
    if total_sum > 0:
        chips = []
        for s in STATUSES:
            v = totals.get(s, 0)
            if v > 0:
                pct = round(v * 100 / total_sum)
                chips.append(f"<span style='color:{COLORS[s]};'>{pct}%</span>")
        st.markdown(f"<div class='percent-row'>{' '.join(chips)}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='percent-row' style='color:#BBBBBB;'>No data</div>", unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(3.8, 3.1), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    labels, sizes, colors = [], [], []
    for s in STATUSES:
        if totals.get(s, 0) > 0:
            labels.append(s); sizes.append(totals[s]); colors.append(COLORS[s])

    if sizes:
        ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            textprops={"color": "white", "weight": "bold"},
            wedgeprops={"linewidth": 2, "edgecolor": DARK_BG},
        )
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", color="white")

    # HELSVART ring rundt pie
    circle = plt.Circle((0, 0), 1.0, fill=False, edgecolor="black", linewidth=3.5, zorder=10)
    ax.add_artist(circle)

    ax.axis("equal")
    st.pyplot(fig, use_container_width=False)

base_log = read_log()
log_now = add_active(base_log)

c1, c2, c3 = st.columns(3)
with c1:
    draw_pie_block("Today",     sum_day(log_now))
with c2:
    draw_pie_block("This Week", sum_week(log_now))
with c3:
    draw_pie_block("This Month",sum_month(log_now))

st.markdown("<br>", unsafe_allow_html=True)

# -------------------- NEDERST: STORE STATUS-KORT --------------------
def status_anchor(text: str, color: str) -> str:
    href = "?set=" + urllib.parse.quote(text)
    return f"<a href='{href}' class='status-card' style='background:{color};'>{text}</a>"

b1, b2, b3, b4 = st.columns(4)
with b1:
    st.markdown(status_anchor("Minor issue", COLORS["Minor issue"]), unsafe_allow_html=True)
with b2:
    st.markdown(status_anchor("Warning",     COLORS["Warning"]),     unsafe_allow_html=True)
with b3:
    st.markdown(status_anchor("Alarm",       COLORS["Alarm"]),       unsafe_allow_html=True)
with b4:
    st.markdown(status_anchor("Urgent",      COLORS["Urgent"]),      unsafe_allow_html=True)

# -------------------- AUTO-REFRESH (UTEN logout) --------------------
# Bruk community-komponenten; den bevarer session state.
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_MS, key="auto-refresh")
except Exception:
    # Fallback: ingen auto-refresh hvis komponenten mangler
    pass

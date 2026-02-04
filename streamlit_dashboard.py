import os
import urllib.parse
from datetime import datetime, timedelta

import requests
import streamlit as st
import matplotlib.pyplot as plt
from streamlit_autorefresh import st_autorefresh

# ---------------------------------
# PAGE CONFIG
# ---------------------------------
st.set_page_config(page_title="Machine Status Dashboard", layout="wide")

DARK_BG = "#2f2f2f"

# ---------------------------------
# GLOBAL CSS  (IDENTISK DESIGN)
# ---------------------------------
st.markdown(
    f"""
    <style>
      .stApp, .main, div.block-container {{
        background-color: {DARK_BG} !important;
      }}
      div.block-container {{
        padding-top: 8px !important;
        max-width: 1500px !important;
      }}

      .status-pill {{
        width: 460px;
        margin: 0 auto 22px auto;
        padding: 18px 12px;
        border-radius: 18px;
        text-align: center;
        font-weight: 800;
        font-size: 32px;
        color: #ffffff;
        border: 4px solid #000000;
      }}

      .pie-title {{
        color: white;
        font-weight: 800;
        font-size: 22px;
        margin: 8px 0 4px 2px;
      }}

      .percent-row {{
        margin: 0 0 8px 2px;
      }}
      .percent-row span {{
        margin-right: 10px;
        font-weight: 800;
        font-size: 15px;
      }}

      .status-card {{
        display: block;
        width: 260px;
        height: 160px;
        border-radius: 18px;
        border: 4px solid #000000;
        text-align:center;
        font-weight: 800;
        font-size: 24px;
        line-height: 160px;
        color: white;
        text-decoration: none;
        transition: 0.09s;
      }}
      .status-card:hover {{ filter: brightness(1.1); transform: translateY(-2px); }}
      .status-card:active {{ transform: translateY(0); filter: brightness(0.9); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------
# CONSTANTS
# ---------------------------------
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

REFRESH_INTERVAL_MS = 2000

# ---------------------------------
# LOGIN SYSTEM
# ---------------------------------
USERNAME = "Massterly"
PASSWORD = "km123"

def login():
    st.markdown("<h1 style='color:white;text-align:center;'>🔒 Login</h1>", unsafe_allow_html=True)
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == USERNAME and p == PASSWORD:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Wrong login")

if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    login()
    st.stop()

# ---------------------------------
# STATUS STATE
# ---------------------------------
if "current_status" not in st.session_state:
    st.session_state["current_status"] = "Up time"
if "status_start" not in st.session_state:
    st.session_state["status_start"] = datetime.now()


# ---------------------------------
# GIST HELPERS
# ---------------------------------
def gist_headers():
    return {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json"
    }

def read_gist():
    """Return entire contents of the Gist file."""
    gist_id = st.secrets["GIST_ID"]
    filename = st.secrets.get("GIST_FILENAME", "statuslog.txt")

    res = requests.get(
        f"https://api.github.com/gists/{gist_id}",
        headers=gist_headers(),
        timeout=10
    )
    res.raise_for_status()

    files = res.json().get("files", {})
    if filename not in files:
        return ""

    raw_url = files[filename]["raw_url"]
    txt = requests.get(raw_url, timeout=10).text
    return txt


def append_gist_line(line: str):
    """Append line to gist (read → append → patch)."""
    gist_id = st.secrets["GIST_ID"]
    filename = st.secrets.get("GIST_FILENAME", "statuslog.txt")

    current = read_gist()
    if current and not current.endswith("\n"):
        current += "\n"
    new_txt = current + line + "\n"

    payload = {"files": {filename: {"content": new_txt}}}

    res = requests.patch(
        f"https://api.github.com/gists/{gist_id}",
        headers=gist_headers(),
        json=payload,
        timeout=10
    )
    res.raise_for_status()


# ---------------------------------
# LOGGING (ONLY GIST)
# ---------------------------------
def write_log(status, start, end):
    line = f"{status}, Start: {start.strftime('%Y-%m-%d %H:%M:%S')}, Slutt: {end.strftime('%Y-%m-%d %H:%M:%S')}"
    append_gist_line(line)

def read_log():
    txt = read_gist()
    entries = []
    for line in txt.splitlines():
        if "Start:" in line and "Slutt:" in line:
            try:
                statuspart, sp, ep = line.split(",")
                status = OLD_TO_NEW.get(statuspart.strip(), statuspart.strip())
                s = datetime.strptime(sp.replace("Start:", "").strip(), "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(ep.replace("Slutt:", "").strip(), "%Y-%m-%d %H:%M:%S")
                entries.append((status, s, e))
            except:
                pass
    return entries


def add_active(log):
    return log + [(st.session_state["current_status"],
                   st.session_state["status_start"],
                   datetime.now())]

# ---------------------------------
# SUMMARIES
# ---------------------------------
def sum_day(log):
    today = datetime.now().date()
    out = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() == today:
            out[status] += (e - s).seconds
    return out

def sum_week(log):
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    out = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() >= monday:
            out[status] += (e - s).seconds
    return out

def sum_month(log):
    now = datetime.now().date()
    mstart = datetime(now.year, now.month, 1)
    out = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() >= mstart:
            out[status] += (e - s).seconds
    return out

# ---------------------------------
# STATUS CHANGE
# ---------------------------------
def change_status(new):
    write_log(st.session_state["current_status"],
              st.session_state["status_start"],
              datetime.now())

    st.session_state["current_status"] = new
    st.session_state["status_start"] = datetime.now()

# Query param support: ?set=Status
qp = st.experimental_get_query_params()
if "set" in qp:
    t = qp["set"][0]
    if t in STATUSES:
        change_status(t)
    st.experimental_set_query_params()   # clear param

# ---------------------------------
# TOP STATUS PILL
# ---------------------------------
curr = st.session_state["current_status"]
st.markdown(
    f"<div class='status-pill' style='background:{COLORS[curr]};'>{curr}</div>",
    unsafe_allow_html=True
)

# ---------------------------------
# PIE BLOCK
# ---------------------------------
def pie_block(title, totals):
    st.markdown(f"<div class='pie-title'>{title}</div>", unsafe_allow_html=True)

    total_sum = sum(totals.values())
    if total_sum:
        chips = []
        for s, v in totals.items():
            if v > 0:
                chips.append(
                    f"<span style='color:{COLORS[s]};'>{round(v*100/total_sum)}%</span>"
                )
        st.markdown(f"<div class='percent-row'>{' '.join(chips)}</div>",
                    unsafe_allow_html=True)
    else:
        st.markdown("<div class='percent-row' style='color:#aaaaaa;'>No data</div>",
                    unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(3.8,3.1), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    labels = []
    sizes = []
    colors = []
    for s in STATUSES:
        val = totals.get(s, 0)
        if val > 0:
            labels.append(s)
            sizes.append(val)
            colors.append(COLORS[s])

    if sizes:
        ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            textprops={"color":"white","weight":"bold"},
            wedgeprops={"linewidth":2,"edgecolor":DARK_BG},
        )
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", color="white")

    circle = plt.Circle((0,0), 1.0, fill=False, edgecolor="black", linewidth=3)
    ax.add_artist(circle)

    ax.axis("equal")
    st.pyplot(fig)

# ---------------------------------
# PIE ROW
# ---------------------------------
entries = read_log()
entries_active = add_active(entries)

c1, c2, c3 = st.columns(3)
with c1: pie_block("Today",      sum_day(entries_active))
with c2: pie_block("This Week",  sum_week(entries_active))
with c3: pie_block("This Month", sum_month(entries_active))

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------
# STATUS BUTTONS (BOTTOM)
# ---------------------------------
def status_card(text, color):
    return (
        f"<a class='status-card' href='?set={urllib.parse.quote(text)}' "
        f"style='background:{color};'>{text}</a>"
    )

b1, b2, b3, b4 = st.columns(4)
with b1: st.markdown(status_card("Minor issue",COLORS["Minor issue"]),unsafe_allow_html=True)
with b2: st.markdown(status_card("Warning",COLORS["Warning"]),unsafe_allow_html=True)
with b3: st.markdown(status_card("Alarm",COLORS["Alarm"]),unsafe_allow_html=True)
with b4: st.markdown(status_card("Urgent",COLORS["Urgent"]),unsafe_allow_html=True)

# ---------------------------------
# AUTO REFRESH
# ---------------------------------
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto")

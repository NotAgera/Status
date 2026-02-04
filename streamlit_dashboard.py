import os
import urllib.parse
from datetime import datetime, timedelta, time

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
# GLOBAL CSS
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
      }}
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
# LOGIN
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
# STATE
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
        "Accept": "application/vnd.github+json",
    }

@st.cache_data(ttl=5)
def read_gist():
    gist_id = st.secrets["GIST_ID"]
    filename = st.secrets.get("GIST_FILENAME", "statuslog.txt")

    res = requests.get(
        f"https://api.github.com/gists/{gist_id}",
        headers=gist_headers(),
        timeout=10,
    )
    res.raise_for_status()

    files = res.json().get("files", {})
    if filename not in files:
        return ""

    return requests.get(files[filename]["raw_url"], timeout=10).text


def append_gist_line(line: str):
    gist_id = st.secrets["GIST_ID"]
    filename = st.secrets.get("GIST_FILENAME", "statuslog.txt")

    current = read_gist()
    if current and not current.endswith("\n"):
        current += "\n"

    payload = {"files": {filename: {"content": current + line + "\n"}}}

    res = requests.patch(
        f"https://api.github.com/gists/{gist_id}",
        headers=gist_headers(),
        json=payload,
        timeout=10,
    )
    res.raise_for_status()
    read_gist.clear()

# ---------------------------------
# LOGGING
# ---------------------------------
def write_log(status, start, end):
    line = f"{status}, Start: {start:%Y-%m-%d %H:%M:%S}, Slutt: {end:%Y-%m-%d %H:%M:%S}"
    append_gist_line(line)

def read_log():
    txt = read_gist()
    entries = []
    for line in txt.splitlines():
        try:
            parts = line.split(",", 2)
            if len(parts) != 3:
                continue
            status_raw, sp, ep = parts
            status = OLD_TO_NEW.get(status_raw.strip(), status_raw.strip())
            s = datetime.strptime(sp.replace("Start:", "").strip(), "%Y-%m-%d %H:%M:%S")
            e = datetime.strptime(ep.replace("Slutt:", "").strip(), "%Y-%m-%d %H:%M:%S")
            entries.append((status, s, e))
        except Exception:
            pass
    return entries

def add_active(log):
    return log + [
        (
            st.session_state["current_status"],
            st.session_state["status_start"],
            datetime.now(),
        )
    ]

# ---------------------------------
# TIME HELPERS
# ---------------------------------
def overlap_seconds(s, e, start, end):
    latest_start = max(s, start)
    earliest_end = min(e, end)
    return max(0, (earliest_end - latest_start).total_seconds())

def summarize(log, start, end):
    out = {s: 0 for s in STATUSES}
    for status, s, e in log:
        out[status] += overlap_seconds(s, e, start, end)
    return out

# ---------------------------------
# STATUS CHANGE
# ---------------------------------
def change_status(new):
    if new == st.session_state["current_status"]:
        return
    write_log(
        st.session_state["current_status"],
        st.session_state["status_start"],
        datetime.now(),
    )
    st.session_state["current_status"] = new
    st.session_state["status_start"] = datetime.now()

qp = st.experimental_get_query_params()
if "set" in qp:
    t = qp["set"][0]
    if t in STATUSES:
        change_status(t)
    st.experimental_set_query_params()

# ---------------------------------
# UI
# ---------------------------------
curr = st.session_state["current_status"]
st.markdown(
    f"<div class='status-pill' style='background:{COLORS[curr]};'>{curr}</div>",
    unsafe_allow_html=True,
)

def pie_block(title, totals):
    st.markdown(f"<div class='pie-title'>{title}</div>", unsafe_allow_html=True)

    total = sum(totals.values())
    if total:
        chips = [
            f"<span style='color:{COLORS[s]};'>{round(v*100/total)}%</span>"
            for s, v in totals.items()
            if v > 0
        ]
        st.markdown(f"<div class='percent-row'>{' '.join(chips)}</div>", unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(3.8, 3.1), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    sizes = [totals[s] for s in STATUSES if totals[s] > 0]
    labels = [s for s in STATUSES if totals[s] > 0]
    colors = [COLORS[s] for s in labels]

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

    ax.axis("equal")
    st.pyplot(fig)

# ---------------------------------
# SUMMARIES
# ---------------------------------
entries = add_active(read_log())
now = datetime.now()

today_start = datetime.combine(now.date(), time.min)
week_start = today_start - timedelta(days=today_start.weekday())
month_start = today_start.replace(day=1)

c1, c2, c3 = st.columns(3)
with c1: pie_block("Today", summarize(entries, today_start, now))
with c2: pie_block("This Week", summarize(entries, week_start, now))
with c3: pie_block("This Month", summarize(entries, month_start, now))

# ---------------------------------
# BUTTONS
# ---------------------------------
def status_card(text):
    return (
        f"<a class='status-card' href='?set={urllib.parse.quote(text)}' "
        f"style='background:{COLORS[text]};'>{text}</a>"
    )

b1, b2, b3, b4 = st.columns(4)
with b1: st.markdown(status_card("Minor issue"), unsafe_allow_html=True)
with b2: st.markdown(status_card("Warning"), unsafe_allow_html=True)
with b3: st.markdown(status_card("Alarm"), unsafe_allow_html=True)
with b4: st.markdown(status_card("Urgent"), unsafe_allow_html=True)

# ---------------------------------
# AUTO REFRESH
# ---------------------------------
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto")

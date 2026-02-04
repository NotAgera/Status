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
# GLOBAL CSS (IDENTISK STIL)
# ---------------------------------
st.markdown(
    f"""
    <style>
      .stApp, .main, div.block-container {{
        background-color: {DARK_BG} !important;
      }}
      div.block-container {{
        padding-top: 8px;
        max-width: 1400px;
      }}

      .status-pill {{
        width: 460px;
        margin: 0 auto 20px auto;
        padding: 18px;
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
        margin: 4px 0 4px 2px;
      }}

      .percent-row {{
        margin: 0 0 6px 4px;
      }}
      .percent-row span {{
        margin-right: 12px;
        font-weight: 800;
        font-size: 15px;
      }}

      .status-card {{
        display: block;
        width: 280px;
        height: 180px;
        border-radius: 18px;
        border: 4px solid #000000;
        text-align:center;
        font-weight: 800;
        font-size: 26px;
        line-height: 180px;
        color: white;
        text-decoration: none;
        transition: 0.08s ease-in-out;
      }}
      .status-card:hover {{
        filter: brightness(1.1);
        transform: translateY(-2px);
      }}
      .status-card:active {{
        transform: translateY(0);
        filter: brightness(0.9);
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

REFRESH_MS = 2000

# ---------------------------------
# LOGIN
# ---------------------------------
USERNAME = "Massterly"
PASSWORD = "km123"

def login_page():
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
    login_page()
    st.stop()

# ---------------------------------
# STATE
# ---------------------------------
if "current_status" not in st.session_state:
    st.session_state["current_status"] = "Up time"
if "status_start" not in st.session_state:
    st.session_state["status_start"] = datetime.now()

# ---------------------------------
# GIST CONFIG (YOU PUT THESE IN STREAMLIT SECRETS)
# ---------------------------------
def gist_enabled():
    return "GITHUB_TOKEN" in st.secrets and "GIST_ID" in st.secrets

def gist_headers():
    return {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json"
    }

def gist_filename():
    return st.secrets.get("GIST_FILENAME", "statuslog.txt")

# ---------------------------------
# READ/WRITE TO GIST
# ---------------------------------
def gist_read():
    gid = st.secrets["GIST_ID"]
    r = requests.get(f"https://api.github.com/gists/{gid}", headers=gist_headers(), timeout=10)
    r.raise_for_status()

    files = r.json()["files"]
    fn = gist_filename()

    if fn not in files:
        return ""

    raw_url = files[fn]["raw_url"]
    r2 = requests.get(raw_url, timeout=10)
    r2.raise_for_status()

    return r2.text

def gist_write_line(line: str):
    gid = st.secrets["GIST_ID"]
    fn = gist_filename()

    current = gist_read()

    if current and not current.endswith("\n"):
        current += "\n"

    new_content = current + line + "\n"

    payload = {"files": {fn: {"content": new_content}}}

    r = requests.patch(
        f"https://api.github.com/gists/{gid}",
        headers=gist_headers(),
        json=payload,
        timeout=10
    )
    r.raise_for_status()

# ---------------------------------
# LOGGING API
# ---------------------------------
def write_log(status, start, end):
    line = f"{status}, Start: {start.strftime('%Y-%m-%d %H:%M:%S')}, Slutt: {end.strftime('%Y-%m-%d %H:%M:%S')}"
    if gist_enabled():
        gist_write_line(line)
    else:
        # SHOULD NEVER HAPPEN NOW, BUT SAFE GUARD
        with open("statuslog.txt", "a") as f:
            f.write(line + "\n")

def read_log():
    if gist_enabled():
        txt = gist_read()
    else:
        txt = open("statuslog.txt").read() if os.path.exists("statuslog.txt") else ""

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
    return log + [(st.session_state["current_status"], st.session_state["status_start"], datetime.now())]

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
    now = datetime.now()
    mstart = datetime(now.year, now.month, 1).date()
    out = {s: 0 for s in STATUSES}
    for status, s, e in log:
        if s.date() >= mstart:
            out[status] += (e - s).seconds
    return out

# ---------------------------------
# STATUS CHANGE
# ---------------------------------
def change_status(new):
    write_log(st.session_state["current_status"], st.session_state["status_start"], datetime.now())
    st.session_state["current_status"] = new
    st.session_state["status_start"] = datetime.now()

qp = st.experimental_get_query_params()
if "set" in qp:
    target = qp["set"][0]
    if target in STATUSES:
        change_status(target)
    st.experimental_set_query_params()

# ---------------------------------
# TOP STATUS PILL
# ---------------------------------
curr = st.session_state["current_status"]
st.markdown(f"<div class='status-pill' style='background:{COLORS[curr]};'>{curr}</div>", unsafe_allow_html=True)

# ---------------------------------
# PIE GENERATOR
# ---------------------------------
def draw_pie_block(title, totals):
    st.markdown(f"<div class='pie-title'>{title}</div>", unsafe_allow_html=True)

    total_sum = sum(totals.values())

    if total_sum:
        chips = [f"<span style='color:{COLORS[s]};'>{round(v*100/total_sum)}%</span>"
                 for s, v in totals.items() if v > 0]
        st.markdown(f"<div class='percent-row'>{' '.join(chips)}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='percent-row' style='color:#aaaaaa;'>No data</div>", unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(3.8, 3.1), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    labels = []
    sizes = []
    colors = []
    for s in STATUSES:
        if totals.get(s, 0) > 0:
            labels.append(s)
            sizes.append(totals[s])
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
        ax.text(0.5,0.5,"No data",ha="center",va="center",color="white")

    # Black outline ring
    circle = plt.Circle((0,0), 1.0, fill=False, edgecolor="black", linewidth=3, zorder=10)
    ax.add_artist(circle)

    ax.axis("equal")
    st.pyplot(fig)

# ---------------------------------
# PIE ROW
# ---------------------------------
entries = read_log()
entries_active = add_active(entries)

c1, c2, c3 = st.columns(3)
with c1: draw_pie_block("Today", sum_day(entries_active))
with c2: draw_pie_block("This Week", sum_week(entries_active))
with c3: draw_pie_block("This Month", sum_month(entries_active))

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------
# BOTTOM STATUS CARDS
# ---------------------------------
def status_card(text):
    href = "?set=" + urllib.parse.quote(text)
    return f"<a class='status-card' href='{href}' style='background:{COLORS[text]};'>{text}</a>"

b1, b2, b3, b4 = st.columns(4)
=True)
with b2: st.markdown(status_card("Warning"),     unsafe_allow_html=True)
with b3: st.markdown(status_card("Alarm"),       unsafe_allow_html=True)
with b4: st.markdown(status_card("Urgent"),      unsafe_allow_html=True)

# ---------------------------------
# AUTO-REFRESH (BEVARER LOGIN)
# ---------------------------------
st_autorefresh(interval=2000, key="auto")

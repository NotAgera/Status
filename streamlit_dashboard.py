import os
import urllib.parse
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import streamlit as st

# -------------------- PAGE CONFIG (før noe annet) --------------------
st.set_page_config(page_title="Machine Status Dashboard",
                   layout="wide",
                   initial_sidebar_state="collapsed")

# -------------------- THEME / CSS --------------------
DARK_BG = "#2f2f2f"

st.markdown(
    f"""
    <style>
      /* Global bakgrunn og layoutbredde */
      .stApp, .main, div.block-container {{
        background-color: {DARK_BG} !important;
      }}
      div.block-container {{
        padding-top: 12px;
        max-width: 1400px;
      }}

      /* Status-pill på toppen */
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

      /* Tittel over pie og prosent-chips */
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

      /* Pie-figur wrapper (gir litt luft) */
      .pie-wrap {{
        background: {DARK_BG};
        border-radius: 12px;
        padding: 6px;
      }}

      /* Store statuskort nederst */
      .status-card {{
        width: 260px;
        height: 160px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 24px;
        color: #ffffff;
        border: 3px solid #000000;
        text-decoration: none;
        transition: filter .08s ease-in-out, transform .08s ease-in-out;
        user-select: none;
      }}
      .status-card:hover {{
        filter: brightness(1.06);
        transform: translateY(-1px);
      }}
      .status-card:active {{
        transform: translateY(0px);
        filter: brightness(0.98);
      }}

      /* Midtstilt hovedtittel */
      .page-title {{
        text-align:center;
        color:#ffffff;
        font-weight:800;
        margin-top: 0;
        margin-bottom: 12px;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- KONSTANTER / FARGER --------------------
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
REFRESH_SECS = 2

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

# -------------------- LOGG I/O --------------------
def write_log(status, start, end):
    with open(LOG_FILE, "a") as f:
        f.write(f"{status}, Start: {start.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"Slutt: {end.strftime('%Y-%m-%d %H:%M:%S')}\n")

def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            if "Start:" in line and "Slutt:" in line:
                try:
                    statuspart, s_part, e_part = line.split(",")
                    status = OLD_TO_NEW.get(statuspart.strip(), statuspart.strip())
                    s = datetime.strptime(
                        s_part.replace("Start:", "").strip(), "%Y-%m-%d %H:%M:%S"
                    )
                    e = datetime.strptime(
                        e_part.replace("Slutt:", "").strip(), "%Y-%m-%d %H:%M:%S"
                    )
                    entries.append((status, s, e))
                except:
                    pass
    return entries

def add_active(log):
    return log + [(st.session_state["current_status"],
                   st.session_state["status_start"],
                   datetime.now())]

# -------------------- SUM FUNKSJONER --------------------
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

# støtte for klikk via query param (?set=Status+Name)
qp = st.experimental_get_query_params()
if "set" in qp:
    new_val = qp["set"][0]
    if new_val in STATUSES:
        change_status(new_val)
    # tøm query params, så vi ikke blir værende i loop
    st.experimental_set_query_params()

# -------------------- TOPP: STATUS-PILL --------------------
curr = st.session_state["current_status"]
pill = f"<div class='status-pill' style='background:{COLORS[curr]};'>{curr}</div>"
st.markdown(pill, unsafe_allow_html=True)

# -------------------- PLOTS: 3 PIES --------------------
st.markdown("<h2 class='page-title' style='margin-top:0;'> </h2>", unsafe_allow_html=True)

def draw_pie_block(title: str, totals: dict):
    # tittel
    st.markdown(f"<div class='pie-title'>{title}</div>", unsafe_allow_html=True)

    # prosent-chips horisontalt (kun de >0)
    total_sum = sum(totals.values())
    if total_sum > 0:
        spans = []
        for s in STATUSES:
            val = totals.get(s, 0)
            if val > 0:
                pct = round(val * 100 / total_sum)
                spans.append(f"<span style='color:{COLORS[s]};'>{pct}%</span>")
        st.markdown(f"<div class='percent-row'>{' '.join(spans)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='percent-row' style='color:#BBBBBB;'>No data</div>", unsafe_allow_html=True)

    # pie
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

    # svart ring rundt hele sirkelen
    circle = plt.Circle((0, 0), 1.0, fill=False, edgecolor="black", linewidth=3.5, zorder=10)
    ax.add_artist(circle)

    ax.axis("equal")
    st.pyplot(fig, use_container_width=False)

# data
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
# Vi bruker lenker med query param (?set=Status) for å slippe widget-flicker
def status_card_html(text: str, color: str) -> str:
    href = "?set=" + urllib.parse.quote(text)
    return f"<a class='status-card' href='{href}' style='background:{color};'>{text}</a>"

b1, b2, b3, b4 = st.columns(4)
with b1:
    st.markdown(status_card_html("Minor issue", COLORS["Minor issue"]), unsafe_allow_html=True)
with b2:
    st.markdown(status_card_html("Warning",     COLORS["Warning"]),     unsafe_allow_html=True)
with b3:
    st.markdown(status_card_html("Alarm",       COLORS["Alarm"]),       unsafe_allow_html=True)
with b4:
    st.markdown(status_card_html("Urgent",      COLORS["Urgent"]),      unsafe_allow_html=True)

# -------------------- AUTO-REFRESH (stabil – uten crash) --------------------
# Prøv community-komponenten hvis tilgjengelig, ellers fall-back til meta refresh.
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_SECS * 1000, key="auto")
except Exception:
    # Meta refresh i <head> – enkel og stabil
    st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SECS}'>", unsafe_allow_html=True)

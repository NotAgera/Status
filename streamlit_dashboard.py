import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

# ============================================================
# ----------------------  LOGIN SECTION  ----------------------
# ============================================================

USERNAME = "Massterly"
PASSWORD = "km123"

def login_screen():
    st.title("🔒 Login")
    st.write("Access restricted. Please log in.")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        if user == USERNAME and pw == PASSWORD:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Incorrect username or password")


# If not logged in → show login screen
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_screen()
    st.stop()

# ============================================================
# ------------------  DASHBOARD STARTS HERE  ------------------
# ============================================================

st.set_page_config(page_title="Machine Status Dashboard", layout="wide")

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

# GLOBAL state stored server-side
if "current_status" not in st.session_state:
    st.session_state["current_status"] = "Up time"
if "status_start" not in st.session_state:
    st.session_state["status_start"] = datetime.now()

# ============================================================
# ------------------------ LOGGING ----------------------------
# ============================================================

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
                    s = datetime.strptime(s_part.replace("Start:", "").strip(), "%Y-%m-%d %H:%M:%S")
                    e = datetime.strptime(e_part.replace("Slutt:", "").strip(), "%Y-%m-%d %H:%M:%S")
                    entries.append((status, s, e))
                except:
                    pass
    return entries


def add_active(log):
    """Include the currently running status as ongoing."""
    return log + [(st.session_state["current_status"],
                   st.session_state["status_start"],
                   datetime.now())]


# ============================================================
# -------------- SUMMARIES (DAY / WEEK / MONTH) --------------
# ============================================================

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


# ============================================================
# ----------------- PIE CHART COMPONENT -----------------------
# ============================================================

def draw_pie(title, totals):
    fig, ax = plt.subplots(figsize=(5, 4), facecolor="#2f2f2f")
    ax.set_facecolor("#2f2f2f")

    total_sum = sum(totals.values())
    labels = []
    sizes = []
    colors = []

    for s in STATUSES:
        if totals[s] > 0:
            labels.append(s)
            sizes.append(totals[s])
            colors.append(COLORS[s])

    if sizes:
        ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            textprops={"color": "white", "weight": "bold"},
            wedgeprops={"linewidth": 2, "edgecolor": "#2f2f2f"},
        )
    else:
        ax.text(0.5, 0.5, "No data", ha="center", color="white")

    # Add black circle border
    circle = plt.Circle((0, 0), 1.0, fill=False, edgecolor="black", linewidth=4)
    ax.add_artist(circle)

    ax.set_title(title, color="white", fontsize=18)
    ax.axis("equal")

    st.pyplot(fig)


# ============================================================
# ---------------------- STATUS BUTTONS -----------------------
# ============================================================

st.markdown(
    "<h1 style='text-align:center; color:white;'>Machine Status Dashboard</h1>",
    unsafe_allow_html=True
)

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

def change_status(new_status):
    # Finish previous log entry
    write_log(
        st.session_state["current_status"],
        st.session_state["status_start"],
        datetime.now()
    )
    # Start new one
    st.session_state["current_status"] = new_status
    st.session_state["status_start"] = datetime.now()

button_specs = [
    ("Up time", col1),
    ("Minor issue", col2),
    ("Warning", col3),
    ("Alarm", col4),
    ("Urgent", col5)
]

for status, col in button_specs:
    with col:
        st.markdown(
            f"""
            <div style="background-color:{COLORS[status]};
                        padding:25px; border-radius:15px;
                        text-align:center; cursor:pointer;">
                <h3 style="color:white;">{status}</h3>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button(f"Select {status}", key=status):
            change_status(status)


# ============================================================
# ------------------ PIE CHART GRID (3x1) --------------------
# ============================================================

log = read_log()
log = add_active(log)

colA, colB, colC = st.columns(3)

with colA:
    draw_pie("Today", sum_day(log))
with colB:
    draw_pie("This Week", sum_week(log))
with colC:
    draw_pie("This Month", sum_month(log))

# Auto-refresh every 2 seconds
st.experimental_rerun()

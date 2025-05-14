import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# Set page config at the very top
st.set_page_config(page_title="Topic Manager", layout="wide")

# Simple login
def login():
    st.sidebar.title("🔐 Login")
    password = st.sidebar.text_input("Enter Password", type="password")
    if password != "admin123":
        st.warning("Incorrect password")
        st.stop()

login()

# Connect to SQLite database
conn = sqlite3.connect("topics.db", check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS major_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
)''')

c.execute('''CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    major_topic_id INTEGER,
    covered BOOLEAN DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (major_topic_id) REFERENCES major_topics(id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    timestamp TEXT
)''')

conn.commit()

# Utility functions
def log_activity(action):
    c.execute("INSERT INTO activity_log (action, timestamp) VALUES (?, ?)", (action, datetime.now().isoformat()))
    conn.commit()

def get_major_topics():
    return pd.read_sql_query("SELECT * FROM major_topics", conn)

def get_topics():
    return pd.read_sql_query("""
        SELECT t.id, t.name, t.difficulty, mt.name AS major_topic, t.covered, t.created_at, t.updated_at 
        FROM topics t LEFT JOIN major_topics mt ON t.major_topic_id = mt.id
    """, conn)

# Streamlit UI
st.title("🧠 Topic Management Website")

# Navigation
page = st.sidebar.radio("Navigation", ["🏠 Home", "➕ Add Topic", "📂 Filter & Visualize"])

# Last visit logging
if "last_visit" not in st.session_state:
    st.session_state.last_visit = datetime.now().isoformat()
    log_activity("Visited the app")

st.sidebar.write(f"**Last visit:** {st.session_state.last_visit}")

if datetime.now() - datetime.fromisoformat(st.session_state.last_visit) > timedelta(days=1):
    st.sidebar.info("⏰ It's been a while! Time to study some topics.")

# HOME PAGE
if page == "🏠 Home":
    st.header("Welcome to Topic Manager")
    st.write("Use the sidebar to navigate:")
    st.markdown("- ➕ **Add Topic** to enter new topics.")
    st.markdown("- 📂 **Filter & Visualize** topics by major category and view difficulty-wise charts.")

# ADD TOPIC PAGE
elif page == "➕ Add Topic":
    st.header("Add New Topic")

    # Add Major Topic
    st.subheader("➕ Add Major Topic")
    new_major_topic = st.text_input("Enter major topic name")
    if st.button("Add Major Topic"):
        try:
            c.execute("INSERT INTO major_topics (name) VALUES (?)", (new_major_topic.strip(),))
            conn.commit()
            log_activity(f"Added major topic: {new_major_topic}")
            st.success("Major topic added")
        except sqlite3.IntegrityError:
            st.error("Major topic already exists")

    # Delete Major Topic
    st.subheader("🗑 Delete Major Topic")
    major_topics_df = get_major_topics()
    major_to_delete = st.selectbox("Select major topic to delete", major_topics_df["name"].tolist())
    if st.button("Delete Major Topic"):
        # Check if any topics are using this major_topic_id
        major_id = int(major_topics_df[major_topics_df.name == major_to_delete]["id"].values[0])
        c.execute("SELECT COUNT(*) FROM topics WHERE major_topic_id = ?", (major_id,))
        topic_count = c.fetchone()[0]
        if topic_count > 0:
            st.warning(f"⚠️ Cannot delete: {topic_count} topic(s) linked to this major topic.")
        else:
            c.execute("DELETE FROM major_topics WHERE id = ?", (major_id,))
            conn.commit()
            log_activity(f"Deleted major topic: {major_to_delete}")
            st.success("Major topic deleted")

    # Add Topic
    st.subheader("📌 Add Topic")
    topic_name = st.text_input("Topic Name")
    difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
    major_topic = st.selectbox("Major Topic", ["None"] + major_topics_df["name"].tolist())

    if st.button("Add Topic"):
        if topic_name:
            major_topic_id = None
            if major_topic != "None":
                major_topic_id = int(major_topics_df[major_topics_df.name == major_topic]["id"].values[0])
            c.execute("""
                INSERT INTO topics (name, difficulty, major_topic_id, covered, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
            """, (topic_name.strip(), difficulty, major_topic_id, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            log_activity(f"Added topic: {topic_name}")
            st.success("Topic added")
        else:
            st.error("Topic name is required")

# FILTER PAGE
elif page == "📂 Filter & Visualize":
    st.header("Filter Topics by Major Topic & Visualize")
    major_topics_df = get_major_topics()
    filter_major_topic = st.selectbox("Select Major Topic", ["All"] + major_topics_df["name"].tolist())
    
    # Search Feature
    search_query = st.text_input("🔍 Search topic by name")

    topics_df = get_topics()
    if filter_major_topic != "All":
        topics_df = topics_df[topics_df["major_topic"] == filter_major_topic]
    if search_query:
        topics_df = topics_df[topics_df["name"].str.contains(search_query, case=False)]

    # Difficulty-Wise Display
    st.subheader("📋 Difficulty-Wise Topics")
    if not topics_df.empty:
        for diff in ["Easy", "Medium", "Hard"]:
            filtered = topics_df[topics_df.difficulty == diff]
            if not filtered.empty:
                with st.expander(f"📘 {diff} Topics ({len(filtered)})", expanded=True):
                    for index, row in filtered.iterrows():
                        with st.container():
                            col1, col2, col3, col4, col5 = st.columns([4, 2, 2, 2, 2])
                            with col1:
                                st.markdown(f"**{row['name']}**")
                                if row['major_topic']:
                                    st.caption(f"Major: {row['major_topic']}")
                            with col2:
                                if st.checkbox("Covered", value=row['covered'], key=f"covered_{row['id']}"):
                                    c.execute("UPDATE topics SET covered = 1, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), row['id']))
                                else:
                                    c.execute("UPDATE topics SET covered = 0, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), row['id']))
                                conn.commit()
                            with col3:
                                if st.button("🗑 Delete", key=f"delete_{row['id']}"):
                                    c.execute("DELETE FROM topics WHERE id = ?", (row['id'],))
                                    conn.commit()
                                    log_activity(f"Deleted topic: {row['name']}")
                                    st.rerun()
                            with col4:
                                st.caption(f"🕒 Created: {row['created_at'].split('T')[0]}")
                            with col5:
                                new_diff = st.selectbox("Change Difficulty", ["", "Easy", "Medium", "Hard"], key=f"diff_change_{row['id']}")
                                if new_diff and new_diff != row['difficulty']:
                                    if st.button("✔️ Update", key=f"update_diff_{row['id']}"):
                                        c.execute("UPDATE topics SET difficulty = ?, updated_at = ? WHERE id = ?", (new_diff, datetime.now().isoformat(), row['id']))
                                        conn.commit()
                                        log_activity(f"Changed difficulty for topic '{row['name']}' to {new_diff}")
                                        st.rerun()

        # Visualization
        st.subheader("📊 Visualization")
        difficulty_counts = topics_df["difficulty"].value_counts().reset_index()
        difficulty_counts.columns = ["Difficulty", "Count"]

        pie_chart = px.pie(difficulty_counts, names="Difficulty", values="Count", title="Topic Distribution by Difficulty")
        bar_chart = px.bar(difficulty_counts, x="Difficulty", y="Count", title="Number of Topics per Difficulty", color="Difficulty")

        st.plotly_chart(pie_chart)
        st.plotly_chart(bar_chart)

        # CSV Export
        csv = topics_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Topics as CSV", data=csv, file_name="topics.csv", mime="text/csv")
    else:
        st.info("No topics available for the selected filters.")

# Activity Log
st.sidebar.header("📜 Activity Log")
activity_df = pd.read_sql_query("SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 10", conn)
st.sidebar.dataframe(activity_df, use_container_width=True)

conn.close()

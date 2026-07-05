import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Page Configuration (Browser Tab Title & Layout)
st.set_page_config(page_title="Sarkari Job Tracker", page_icon="💼", layout="wide")

# Custom Styling for clean UI
st.markdown("""
    <style>
    .main-title { font-size:42px !important; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .sub-title { font-size:18px !important; color: #4B5563; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="main-title">🎯 Live Sarkari Job & Exam Notification Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Yeh dashboard automatic har 4 ghante mein AI aur Cloud Scraper ke through processed live data dikhata hai.</div>', unsafe_allow_html=True)

# 🔐 Supabase Credentials Streamlit Secrets se uthana
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("❌ Streamlit Secrets mein Supabase keys nahi mili! Advanced Settings check karein.")
    st.stop()

# Data Load karne ka function
def load_live_data():
    try:
        # Exams table se saara data naye ke hisab se sort karke laayein
        response = supabase.table("exams").select("*").order("created_at", descending=True).execute()
        return response.data
    except Exception as e:
        st.error(f"❌ Database connection error: {e}")
        return []

# Sidebar for controls
st.sidebar.header("⚙️ Controls")
if st.sidebar.button("🔄 Refresh Data", type="primary", use_container_width=True):
    st.toast("Fetching latest data from Supabase Cloud...")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Table ke upar kisi bhi column par click karke aap data ko sort kar sakte hain.")

# Main Display Logic
live_data = load_live_data()

if not live_data:
    st.warning("ℹ️ Database abhi khali hai ya connection pending hai. Bot ke agle run ka wait karein.")
else:
    # Pandas DataFrame mein convert karein beautiful presentation ke liye
    df = pd.DataFrame(live_data)
    
    # Faltu internal columns clean karein jo user ko nahi dikhane
    columns_to_drop = ["id", "created_at"]
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns], errors='ignore')
    
    # Columns ke naam standard aur clear karein
    rename_mapping = {
        "notice_subject": "Notice Subject",
        "department": "Department / Board",
        "form_status": "Form Status",
        "start_date": "Start Date",
        "last_date": "Last Date",
        "exam_date": "Exam Date"
    }
    df = df.rename(columns=rename_mapping)
    
    # Active forms ki counting metric dikhane ke liye
    st.success(f"📊 Total **{len(df)}** Active Recruitment Notifications Live Right Now!")
    
    # Display the clean interactive data table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
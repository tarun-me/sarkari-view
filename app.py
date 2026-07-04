import streamlit as st
import pandas as pd
import json
import os

st.set_page_config(page_title="Sarkari Job Alerts", layout="wide")

st.title("🚀 Sarkari Job Alerts Dashboard")
st.write("Hamara AI engine background mein naye notices check kar raha hai...")

# Database file ka naam
db_filename = "sarkari_database.json"

if os.path.exists(db_filename):
    with open(db_filename, "r") as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Table dikhana
    st.table(df)
else:
    st.warning("Abhi tak koi naya job notice save nahi hua hai. Backend pipeline run karein!")
if st.sidebar.button("Refresh Data"):
    st.rerun()
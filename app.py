import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="PMSG Inspection Pending",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ PMSG Inspection Pending Dashboard")

st.subheader("Upload PMSG Inspection Pending Export")

uploaded_file = st.file_uploader(
    "Upload PMSG Excel Export",
    type=["xlsx", "xls", "csv"]
)

if uploaded_file is not None:

    try:

        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success(
            f"File uploaded successfully: {uploaded_file.name}"
        )

        st.metric(
            "Total Records",
            f"{len(df):,}"
        )

        st.subheader("Available Columns")

        st.write(list(df.columns))

        st.subheader("Uploaded Data")

        st.dataframe(
            df,
            use_container_width=True,
            height=500
        )

    except Exception as e:

        st.error(
            f"Error while reading file: {e}"
        )

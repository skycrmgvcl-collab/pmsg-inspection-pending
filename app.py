import streamlit as st
import pandas as pd
import io
import re
from datetime import date


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="PMSG Inspection Pending Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONSTANTS
# ============================================================

AGEING_ORDER = [
    "0-3 Days",
    "4-7 Days",
    "8-15 Days",
    "16-30 Days",
    ">30 Days"
]

SUMMARY_COLUMNS = [
    "S/DN",
    "0-3 Days",
    "4-7 Days",
    "8-15 Days",
    "16-30 Days",
    ">30 Days",
    "Total"
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_column_name(column):
    """Normalize column name for matching."""

    column = str(column).strip().upper()
    column = column.replace("_", " ")
    column = re.sub(r"\s+", " ", column)

    return column


def find_column(df, possible_names):
    """Find a column using multiple possible names."""

    normalized = {
        normalize_column_name(col): col
        for col in df.columns
    }

    # Exact matching
    for name in possible_names:

        key = normalize_column_name(name)

        if key in normalized:
            return normalized[key]

    # Partial matching
    for actual_norm, actual_col in normalized.items():

        for name in possible_names:

            name_norm = normalize_column_name(name)

            if (
                name_norm in actual_norm
                or actual_norm in name_norm
            ):
                return actual_col

    return None


# ============================================================
# CLEAN DATA
# ============================================================

def clean_dataframe(df):

    df = df.copy()

    # Remove completely blank rows
    df = df.dropna(how="all")

    # Clean column names
    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    # --------------------------------------------------------
    # Find important columns
    # --------------------------------------------------------

    installation_col = find_column(
        df,
        [
            "Installation Date",
            "Installation_Date",
            "INSTALLATION DATE",
            "InstallationDate"
        ]
    )

    circle_col = find_column(
        df,
        [
            "Circle",
            "Circle Name",
            "CIRCLE"
        ]
    )

    division_col = find_column(
        df,
        [
            "Division",
            "Division Name",
            "DIVISION"
        ]
    )

    sdn_col = find_column(
        df,
        [
            "Sub Division",
            "SubDivision",
            "Sub-Division",
            "S/DN",
            "SDN",
            "Sub Div",
            "Sub Division Name"
        ]
    )

    # --------------------------------------------------------
    # Other useful columns
    # --------------------------------------------------------

    application_col = find_column(
        df,
        [
            "Application Number",
            "Application No",
            "Application No.",
            "ApplicationNumber"
        ]
    )

    consumer_name_col = find_column(
        df,
        [
            "Consumer Name",
            "ConsumerName",
            "Name"
        ]
    )

    consumer_no_col = find_column(
        df,
        [
            "Consumer Number",
            "Consumer No",
            "Consumer No.",
            "ConsumerNumber"
        ]
    )

    mobile_col = find_column(
        df,
        [
            "Mobile Number",
            "Mobile No",
            "Mobile",
            "MobileNumber"
        ]
    )

    # --------------------------------------------------------
    # Installation Date is compulsory
    # --------------------------------------------------------

    if installation_col is None:

        raise ValueError(
            "Installation Date column was not found "
            "in the uploaded Excel file."
        )

    # --------------------------------------------------------
    # Store detected columns
    # --------------------------------------------------------

    column_map = {

        "Installation Date": installation_col,

        "Circle": circle_col,

        "Division": division_col,

        "Sub Division": sdn_col,

        "Application Number": application_col,

        "Consumer Name": consumer_name_col,

        "Consumer Number": consumer_no_col,

        "Mobile Number": mobile_col
    }

    # --------------------------------------------------------
    # Convert Installation Date
    # --------------------------------------------------------

    df["__Installation_Date"] = pd.to_datetime(
        df[installation_col],
        errors="coerce"
    )

    # Remove invalid dates
    df = df[
        df["__Installation_Date"].notna()
    ].copy()

    # --------------------------------------------------------
    # Standard Circle
    # --------------------------------------------------------

    if circle_col:

        df["__Circle"] = (
            df[circle_col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    else:

        df["__Circle"] = "Unknown"

    # --------------------------------------------------------
    # Standard Division
    # --------------------------------------------------------

    if division_col:

        df["__Division"] = (
            df[division_col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    else:

        df["__Division"] = "Unknown"

    # --------------------------------------------------------
    # Standard S/DN
    # --------------------------------------------------------

    if sdn_col:

        df["__SDN"] = (
            df[sdn_col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    else:

        df["__SDN"] = "Unknown"

    return df, column_map


# ============================================================
# CALCULATE AGEING
# ============================================================

def calculate_ageing(df, report_date):

    df = df.copy()

    report_timestamp = pd.Timestamp(
        report_date
    )

    df["Pending Days"] = (
        report_timestamp.normalize()
        - df["__Installation_Date"].dt.normalize()
    ).dt.days

    # Negative values become zero
    df["Pending Days"] = (
        df["Pending Days"]
        .clip(lower=0)
    )

    def get_ageing(days):

        if days <= 3:
            return "0-3 Days"

        elif days <= 7:
            return "4-7 Days"

        elif days <= 15:
            return "8-15 Days"

        elif days <= 30:
            return "16-30 Days"

        else:
            return ">30 Days"

    df["Ageing"] = (
        df["Pending Days"]
        .apply(get_ageing)
    )

    return df


# ============================================================
# CREATE SUMMARY
# ============================================================

def create_summary(df):

    if df.empty:

        return pd.DataFrame(
            columns=SUMMARY_COLUMNS
        )

    summary = pd.crosstab(
        df["__SDN"],
        df["Ageing"]
    )

    # Make sure every ageing column exists
    for col in AGEING_ORDER:

        if col not in summary.columns:

            summary[col] = 0

    summary = summary[
        AGEING_ORDER
    ]

    summary["Total"] = (
        summary.sum(axis=1)
    )

    summary = (
        summary
        .reset_index()
        .rename(
            columns={
                "__SDN": "S/DN"
            }
        )
    )

    summary = (
        summary
        .sort_values("S/DN")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # TOTAL ROW
    # --------------------------------------------------------

    total_row = {
        "S/DN": "TOTAL"
    }

    for col in AGEING_ORDER:

        total_row[col] = int(
            summary[col].sum()
        )

    total_row["Total"] = int(
        summary["Total"].sum()
    )

    summary = pd.concat(
        [
            summary,
            pd.DataFrame([total_row])
        ],
        ignore_index=True
    )

    return summary[
        SUMMARY_COLUMNS
    ]


# ============================================================
# WHATSAPP TABLE
# ============================================================

def format_whatsapp_table(summary):

    if summary.empty:

        return "No pending cases."

    headers = [
        "S/DN",
        "0-3",
        "4-7",
        "8-15",
        "16-30",
        ">30",
        "Total"
    ]

    rows = []

    for _, row in summary.iterrows():

        rows.append(
            [
                str(row["S/DN"]),
                str(int(row["0-3 Days"])),
                str(int(row["4-7 Days"])),
                str(int(row["8-15 Days"])),
                str(int(row["16-30 Days"])),
                str(int(row[">30 Days"])),
                str(int(row["Total"]))
            ]
        )

    widths = []

    for i in range(len(headers)):

        values = [
            headers[i]
        ]

        values += [
            row[i]
            for row in rows
        ]

        widths.append(
            max(
                len(value)
                for value in values
            )
        )

    lines = []

    # Header
    header = (
        f"{headers[0]:<{widths[0]}}  "
        f"{headers[1]:>{widths[1]}}  "
        f"{headers[2]:>{widths[2]}}  "
        f"{headers[3]:>{widths[3]}}  "
        f"{headers[4]:>{widths[4]}}  "
        f"{headers[5]:>{widths[5]}}  "
        f"{headers[6]:>{widths[6]}}"
    )

    lines.append(header)

    lines.append(
        "-" * len(header)
    )

    # Data rows
    for row in rows:

        line = (
            f"{row[0]:<{widths[0]}}  "
            f"{row[1]:>{widths[1]}}  "
            f"{row[2]:>{widths[2]}}  "
            f"{row[3]:>{widths[3]}}  "
            f"{row[4]:>{widths[4]}}  "
            f"{row[5]:>{widths[5]}}  "
            f"{row[6]:>{widths[6]}}"
        )

        lines.append(line)

    return "\n".join(lines)


# ============================================================
# DIVISION WHATSAPP MESSAGE
# ============================================================

def make_division_message(
    division,
    report_date,
    summary
):

    total = 0

    if not summary.empty:

        total_row = summary[
            summary["S/DN"].astype(str).str.upper()
            == "TOTAL"
        ]

        if not total_row.empty:

            total = int(
                total_row.iloc[0]["Total"]
            )

    table = format_whatsapp_table(
        summary
    )

    message = f"""*PMSG INSPECTION PENDING*

Division: *{division}*
Date: *{report_date.strftime("%d-%m-%Y")}*

Total Pending: *{total}*

```text
{table}
```

All concerned S/DNs are requested to attend pending inspections on priority, particularly cases pending for more than 7 days.

Please ensure timely completion and reporting of pending inspections.
"""

    return message


# ============================================================
# S/DN WHATSAPP MESSAGE
# ============================================================

def make_sdn_message(
    sdn,
    division,
    report_date,
    sdn_data
):

    counts = (
        sdn_data["Ageing"]
        .value_counts()
        .to_dict()
    )

    total = len(
        sdn_data
    )

    message = f"""*PMSG INSPECTION PENDING*

*S/DN: {sdn}*

Division: {division}
Date: {report_date.strftime("%d-%m-%Y")}

Total Pending: *{total}*

0–3 Days: {counts.get("0-3 Days", 0)}
4–7 Days: {counts.get("4-7 Days", 0)}
8–15 Days: {counts.get("8-15 Days", 0)}
16–30 Days: {counts.get("16-30 Days", 0)}
>30 Days: {counts.get(">30 Days", 0)}

Please attend pending inspections on priority and complete pending cases at the earliest.

"""

    return message


# ============================================================
# PREPARE DATA FOR EXCEL
# ============================================================

def prepare_export_dataframe(df):

    export_df = df.copy()

    rename_map = {

        "__Circle": "Circle",

        "__Division": "Division",

        "__SDN": "S/DN",

        "__Installation_Date":
            "Installation Date"
    }

    export_df = export_df.rename(
        columns=rename_map
    )

    return export_df


# ============================================================
# CREATE EXCEL
# ============================================================

def dataframe_to_excel(
    df,
    summary
):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter"
    ) as writer:

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False
        )

        # ----------------------------------------------------
        # Complete Pending List
        # ----------------------------------------------------

        export_df = (
            prepare_export_dataframe(df)
        )

        export_df.to_excel(
            writer,
            sheet_name="Pending List",
            index=False
        )

        # ----------------------------------------------------
        # Individual S/DN sheets
        # ----------------------------------------------------

        if "__SDN" in df.columns:

            unique_sdns = sorted(
                df["__SDN"]
                .dropna()
                .unique()
            )

            for sdn in unique_sdns:

                sdn_df = df[
                    df["__SDN"] == sdn
                ].copy()

                sdn_df = (
                    prepare_export_dataframe(
                        sdn_df
                    )
                )

                sheet_name = str(
                    sdn
                )[:31]

                # Remove invalid Excel characters
                sheet_name = re.sub(
                    r"[\[\]\:\*\?\/\\]",
                    "-",
                    sheet_name
                )

                if not sheet_name:
                    sheet_name = "SDN"

                sdn_df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

        # ----------------------------------------------------
        # Basic formatting
        # ----------------------------------------------------

        workbook = writer.book

        header_format = (
            workbook.add_format(
                {
                    "bold": True,
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter"
                }
            )
        )

        # Apply formatting to first row
        for worksheet in writer.sheets.values():

            worksheet.set_row(
                0,
                25
            )

            # Freeze header
            worksheet.freeze_panes(
                1,
                0
            )

    output.seek(0)

    return output


# ============================================================
# APPLICATION HEADER
# ============================================================

st.title(
    "⚡ PMSG Inspection Pending Dashboard"
)

st.caption(
    "PMSG Inspection Pending — MGVCL"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "📂 PMSG Report"
    )

    st.write(
        "Upload the latest PMSG Inspection Pending export."
    )

    uploaded_file = st.file_uploader(
        "Upload PMSG Export",
        type=[
            "xlsx",
            "xls",
            "csv"
        ]
    )

    st.divider()

    report_date = st.date_input(
        "Report Date",
        value=date.today()
    )


# ============================================================
# NO FILE
# ============================================================

if uploaded_file is None:

    st.info(
        "Please upload the latest PMSG Inspection Pending Excel export."
    )

    st.markdown(
        """
        ### Daily Workflow

        **1.** Export Inspection Pending data from PMSG portal.

        **2.** Upload the Excel file here.

        **3.** Select Circle.

        **4.** Select Division.

        **5.** Select Report Date.

        **6.** Click Generate Report.

        **7.** Copy the Division WhatsApp message.

        **8.** Select each S/DN and copy its WhatsApp message.

        **9.** Download the consolidated Division Excel.
        """
    )

    st.stop()


# ============================================================
# READ UPLOADED FILE
# ============================================================

try:

    if uploaded_file.name.lower().endswith(
        ".csv"
    ):

        df = pd.read_csv(
            uploaded_file
        )

    else:

        df = pd.read_excel(
            uploaded_file
        )

except Exception as e:

    st.error(
        f"Unable to read uploaded file: {e}"
    )

    st.stop()


# ============================================================
# CLEAN DATA
# ============================================================

try:

    df, column_map = (
        clean_dataframe(df)
    )

except Exception as e:

    st.error(
        str(e)
    )

    st.subheader(
        "Detected Columns"
    )

    st.write(
        list(df.columns)
    )

    st.stop()


# ============================================================
# FILE SUCCESS
# ============================================================

st.success(
    f"File loaded successfully: {uploaded_file.name}"
)


# ============================================================
# BASIC STATISTICS
# ============================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Valid Records",
    f"{len(df):,}"
)

c2.metric(
    "Circles",
    df["__Circle"].nunique()
)

c3.metric(
    "Divisions",
    df["__Division"].nunique()
)

c4.metric(
    "S/DNs",
    df["__SDN"].nunique()
)


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.divider()

st.sidebar.subheader(
    "📊 Report Selection"
)


# ============================================================
# CIRCLE
# ============================================================

circles = sorted(
    [
        x
        for x in df["__Circle"]
        .dropna()
        .unique()
        if str(x).strip()
    ]
)

if not circles:

    st.error(
        "No Circle data found."
    )

    st.stop()


selected_circle = (
    st.sidebar.selectbox(
        "Circle",
        circles
    )
)


# ============================================================
# DIVISION
# ============================================================

circle_data = df[
    df["__Circle"]
    == selected_circle
].copy()

divisions = sorted(
    [
        x
        for x in circle_data["__Division"]
        .dropna()
        .unique()
        if str(x).strip()
    ]
)

if not divisions:

    st.error(
        "No Division data found for selected Circle."
    )

    st.stop()


selected_division = (
    st.sidebar.selectbox(
        "Division",
        divisions
    )
)


# ============================================================
# DIVISION DATA
# ============================================================

division_data = circle_data[
    circle_data["__Division"]
    == selected_division
].copy()


# ============================================================
# REPORT BUTTON
# ============================================================

st.sidebar.divider()

generate_report = st.sidebar.button(
    "🚀 Generate Report",
    type="primary",
    use_container_width=True
)


# ============================================================
# BEFORE GENERATE
# ============================================================

if not generate_report:

    st.info(
        "Select Circle, Division and Report Date, "
        "then click **Generate Report**."
    )

    st.stop()


# ============================================================
# CALCULATE AGEING
# ============================================================

division_data = calculate_ageing(
    division_data,
    report_date
)


# ============================================================
# REPORT HEADER
# ============================================================

st.divider()

st.header(
    f"📊 {selected_division} — Inspection Pending"
)

st.write(
    f"**Circle:** {selected_circle}"
)

st.write(
    f"**Report Date:** "
    f"{report_date.strftime('%d-%m-%Y')}"
)


# ============================================================
# OVERALL AGEING
# ============================================================

total_pending = len(
    division_data
)

ageing_counts = (
    division_data["Ageing"]
    .value_counts()
    .to_dict()
)


m1, m2, m3, m4, m5, m6 = (
    st.columns(6)
)

m1.metric(
    "Total",
    total_pending
)

m2.metric(
    "0–3 Days",
    ageing_counts.get(
        "0-3 Days",
        0
    )
)

m3.metric(
    "4–7 Days",
    ageing_counts.get(
        "4-7 Days",
        0
    )
)

m4.metric(
    "8–15 Days",
    ageing_counts.get(
        "8-15 Days",
        0
    )
)

m5.metric(
    "16–30 Days",
    ageing_counts.get(
        "16-30 Days",
        0
    )
)

m6.metric(
    ">30 Days",
    ageing_counts.get(
        ">30 Days",
        0
    )
)


# ============================================================
# S/DN SUMMARY
# ============================================================

st.subheader(
    "📋 S/DN-wise Ageing Summary"
)

summary = create_summary(
    division_data
)

st.dataframe(
    summary,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DIVISION WHATSAPP MESSAGE
# ============================================================

st.subheader(
    "📱 Division WhatsApp Message"
)

division_message = (
    make_division_message(
        selected_division,
        report_date,
        summary
    )
)

st.text_area(
    "Copy this message to WhatsApp",
    value=division_message,
    height=350
)

st.download_button(
    "⬇️ Download Division Message",
    data=division_message,
    file_name=(
        f"PMSG_"
        f"{selected_division}_"
        f"{report_date.strftime('%d-%m-%Y')}.txt"
    ),
    mime="text/plain"
)


# ============================================================
# S/DN SECTION
# ============================================================

st.divider()

st.subheader(
    "📋 S/DN-wise Pending List"
)


sdns = sorted(
    division_data["__SDN"]
    .dropna()
    .unique()
)


if not sdns:

    st.warning(
        "No S/DN found."
    )

    st.stop()


selected_sdn = st.selectbox(
    "Select S/DN",
    sdns
)


# ============================================================
# SELECTED S/DN DATA
# ============================================================

sdn_data = division_data[
    division_data["__SDN"]
    == selected_sdn
].copy()


# ============================================================
# S/DN METRICS
# ============================================================

sdn_counts = (
    sdn_data["Ageing"]
    .value_counts()
    .to_dict()
)

st.markdown(
    f"### {selected_sdn}"
)


a1, a2, a3, a4, a5, a6 = (
    st.columns(6)
)

a1.metric(
    "Total",
    len(sdn_data)
)

a2.metric(
    "0–3",
    sdn_counts.get(
        "0-3 Days",
        0
    )
)

a3.metric(
    "4–7",
    sdn_counts.get(
        "4-7 Days",
        0
    )
)

a4.metric(
    "8–15",
    sdn_counts.get(
        "8-15 Days",
        0
    )
)

a5.metric(
    "16–30",
    sdn_counts.get(
        "16-30 Days",
        0
    )
)

a6.metric(
    ">30",
    sdn_counts.get(
        ">30 Days",
        0
    )
)


# ============================================================
# AGEING FILTER
# ============================================================

ageing_filter = st.multiselect(
    "Filter Ageing",
    AGEING_ORDER,
    default=AGEING_ORDER
)


filtered_sdn_data = sdn_data[
    sdn_data["Ageing"].isin(
        ageing_filter
    )
].copy()


# ============================================================
# DETAILED LIST
# ============================================================

st.subheader(
    f"Pending List — {selected_sdn}"
)

st.dataframe(
    filtered_sdn_data,
    use_container_width=True,
    height=550
)


# ============================================================
# S/DN WHATSAPP MESSAGE
# ============================================================

st.subheader(
    "📱 S/DN WhatsApp Message"
)

sdn_message = make_sdn_message(
    selected_sdn,
    selected_division,
    report_date,
    sdn_data
)

st.text_area(
    "Copy this message to WhatsApp",
    value=sdn_message,
    height=350
)

st.download_button(
    "⬇️ Download S/DN Message",
    data=sdn_message,
    file_name=(
        f"PMSG_"
        f"{selected_sdn}_"
        f"{report_date.strftime('%d-%m-%Y')}.txt"
    ),
    mime="text/plain"
)


# ============================================================
# EXCEL DOWNLOAD
# ============================================================

st.divider()

st.subheader(
    "📥 Division Excel"
)

excel_file = dataframe_to_excel(
    division_data,
    summary
)

st.download_button(
    "⬇️ Download Complete Division Excel",
    data=excel_file,
    file_name=(
        f"PMSG_Inspection_Pending_"
        f"{selected_division}_"
        f"{report_date.strftime('%d-%m-%Y')}.xlsx"
    ),
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    use_container_width=True
)


# ============================================================
# COLUMN INFORMATION
# ============================================================

with st.expander(
    "🔎 Detected PMSG Columns"
):

    st.write(
        column_map
    )


with st.expander(
    "📄 Original Uploaded Columns"
):

    st.write(
        list(df.columns)
    )

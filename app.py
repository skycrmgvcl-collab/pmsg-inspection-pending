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

AGEING_COLUMNS = [
    "0-3",
    "4-7",
    "8-15",
    "16-30",
    ">30"
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_column_name(name):
    """
    Normalize column names for reliable matching.
    """
    name = str(name).strip()
    name = name.replace("\n", " ")
    name = re.sub(r"\s+", " ", name)
    return name


def find_column(df, possible_names):
    """
    Find a column from a list of possible column names.
    Matching is case-insensitive and whitespace-insensitive.
    """

    normalized = {
        normalize_column_name(col).lower(): col
        for col in df.columns
    }

    for name in possible_names:
        key = normalize_column_name(name).lower()

        if key in normalized:
            return normalized[key]

    # Partial matching
    for actual_lower, actual_col in normalized.items():
        for name in possible_names:
            target = normalize_column_name(name).lower()

            if target in actual_lower or actual_lower in target:
                return actual_col

    return None


def clean_dataframe(df):
    """
    Clean uploaded PMSG export data and identify required columns.
    """

    df = df.copy()

    # Normalize column names
    df.columns = [
        normalize_column_name(col)
        for col in df.columns
    ]

    # Remove completely empty rows
    df = df.dropna(how="all")

    # --------------------------------------------------------
    # Find important columns
    # --------------------------------------------------------

    installation_col = find_column(
        df,
        [
            "Installation Date",
            "Installation_Date",
            "InstallationDate",
            "Date of Installation"
        ]
    )

    application_col = find_column(
        df,
        [
            "Application Number",
            "Application No",
            "Application_Number",
            "ApplicationNumber"
        ]
    )

    consumer_name_col = find_column(
        df,
        [
            "Consumer Name",
            "Consumer_Name",
            "ConsumerName"
        ]
    )

    consumer_no_col = find_column(
        df,
        [
            "Consumer Number",
            "Consumer No",
            "Consumer_Number",
            "ConsumerNumber"
        ]
    )

    mobile_col = find_column(
        df,
        [
            "Mobile Number",
            "Mobile No",
            "Mobile_Number",
            "MobileNumber"
        ]
    )

    sanction_load_col = find_column(
        df,
        [
            "Sanction Load",
            "Sanction_Load"
        ]
    )

    existing_capacity_col = find_column(
        df,
        [
            "Existing Capacity",
            "Existing_Capacity"
        ]
    )

    proposed_capacity_col = find_column(
        df,
        [
            "Proposed Capacity",
            "Proposed_Capacity"
        ]
    )

    approved_capacity_col = find_column(
        df,
        [
            "Approved Capacity",
            "Approved_Capacity"
        ]
    )

    circle_col = find_column(
        df,
        [
            "Circle",
            "Circle Name",
            "Circle_Name"
        ]
    )

    division_col = find_column(
        df,
        [
            "Division",
            "Division Name",
            "Division_Name"
        ]
    )

    sdn_col = find_column(
        df,
        [
            "Sub Division",
            "Sub Division Name",
            "Sub_Division",
            "Subdivision",
            "Subdivision Name",
            "S/DN",
            "SDN"
        ]
    )

    # --------------------------------------------------------
    # Validate minimum required columns
    # --------------------------------------------------------

    missing = []

    if installation_col is None:
        missing.append("Installation Date")

    if circle_col is None:
        missing.append("Circle")

    if division_col is None:
        missing.append("Division")

    if sdn_col is None:
        missing.append("Sub Division")

    if missing:
        raise ValueError(
            "Required columns not found: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Create standardized columns
    # --------------------------------------------------------

    df["_Installation_Date"] = pd.to_datetime(
        df[installation_col],
        errors="coerce",
        dayfirst=False
    )

    df["_Circle"] = (
        df[circle_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["_Division"] = (
        df[division_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["_SDN"] = (
        df[sdn_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Store original column mappings
    mapping = {
        "Installation Date": installation_col,
        "Application Number": application_col,
        "Consumer Name": consumer_name_col,
        "Consumer Number": consumer_no_col,
        "Mobile Number": mobile_col,
        "Sanction Load": sanction_load_col,
        "Existing Capacity": existing_capacity_col,
        "Proposed Capacity": proposed_capacity_col,
        "Approved Capacity": approved_capacity_col,
        "Circle": circle_col,
        "Division": division_col,
        "Sub Division": sdn_col
    }

    return df, mapping


def calculate_ageing(df, report_date):
    """
    Calculate Pending Days and ageing category.
    """

    df = df.copy()

    df["Pending Days"] = (
        pd.Timestamp(report_date)
        - df["_Installation_Date"]
    ).dt.days

    # Prevent negative ageing
    df["Pending Days"] = df["Pending Days"].fillna(0)

    df.loc[
        df["Pending Days"] < 0,
        "Pending Days"
    ] = 0

    def ageing_category(days):

        if days <= 3:
            return "0-3"

        elif days <= 7:
            return "4-7"

        elif days <= 15:
            return "8-15"

        elif days <= 30:
            return "16-30"

        else:
            return ">30"

    df["Ageing"] = df["Pending Days"].apply(
        ageing_category
    )

    return df


def create_summary(df):
    """
    Create S/DN-wise ageing summary.
    """

    if df.empty:
        return pd.DataFrame(
            columns=[
                "S/DN",
                "0-3",
                "4-7",
                "8-15",
                "16-30",
                ">30",
                "Total",
                ">3 Days"
            ]
        )

    summary = pd.crosstab(
        df["_SDN"],
        df["Ageing"]
    )

    # Make sure every ageing column exists
    for col in AGEING_COLUMNS:

        if col not in summary.columns:
            summary[col] = 0

    summary = summary[AGEING_COLUMNS]

    summary["Total"] = summary[
        AGEING_COLUMNS
    ].sum(axis=1)

    # --------------------------------------------------------
    # MORE THAN 3 DAYS
    #
    # 4-7 + 8-15 + 16-30 + >30
    # --------------------------------------------------------

    summary[">3 Days"] = (
        summary["4-7"]
        + summary["8-15"]
        + summary["16-30"]
        + summary[">30"]
    )

    summary = summary.reset_index()

    summary = summary.rename(
        columns={
            "_SDN": "S/DN"
        }
    )

    # Sort by S/DN
    summary = summary.sort_values(
        by="S/DN"
    ).reset_index(drop=True)

    # Convert numeric columns to int
    numeric_columns = AGEING_COLUMNS + [
        "Total",
        ">3 Days"
    ]

    for col in numeric_columns:
        summary[col] = (
            pd.to_numeric(
                summary[col],
                errors="coerce"
            )
            .fillna(0)
            .astype(int)
        )

    return summary


def create_division_total(summary_df):
    """
    Calculate Division total.
    """

    if summary_df.empty:
        return {
            "0-3": 0,
            "4-7": 0,
            "8-15": 0,
            "16-30": 0,
            ">30": 0,
            "Total": 0,
            ">3 Days": 0
        }

    result = {}

    for col in AGEING_COLUMNS:
        result[col] = int(
            summary_df[col].sum()
        )

    result["Total"] = sum(
        result[col]
        for col in AGEING_COLUMNS
    )

    result[">3 Days"] = (
        result["4-7"]
        + result["8-15"]
        + result["16-30"]
        + result[">30"]
    )

    return result


# ============================================================
# WHATSAPP MESSAGE FUNCTIONS
# ============================================================

def make_division_message(
    summary_df,
    division_name,
    report_date
):
    """
    Create simple S/DN-wise Division WhatsApp message.
    """

    lines = []

    lines.append(
        "*PMSG INSPECTION PENDING*"
    )

    lines.append("")

    lines.append(
        f"*{division_name}*"
    )

    lines.append(
        f"Date: {report_date}"
    )

    lines.append("")

    lines.append(
        "*S/DN-wise Ageing*"
    )

    lines.append("")

    total_pending = 0
    total_over_3 = 0

    for _, row in summary_df.iterrows():

        sdn = str(row["S/DN"])

        d03 = int(row["0-3"])
        d47 = int(row["4-7"])
        d815 = int(row["8-15"])
        d1630 = int(row["16-30"])
        d30 = int(row[">30"])

        total = (
            d03
            + d47
            + d815
            + d1630
            + d30
        )

        over_3 = (
            d47
            + d815
            + d1630
            + d30
        )

        total_pending += total
        total_over_3 += over_3

        lines.append(
            f"*{sdn}*"
        )

        lines.append(
            f"Total: {total} | >3 Days: {over_3}"
        )

        lines.append(
            f"0-3: {d03:02d} | "
            f"4-7: {d47:02d} | "
            f"8-15: {d815:02d} | "
            f"16-30: {d1630:02d} | "
            f">30: {d30:02d}"
        )

        lines.append("")

    lines.append(
        "--------------------------------"
    )

    lines.append("")

    lines.append(
        f"*Division Total: {total_pending}*"
    )

    lines.append(
        f"*>3 Days: {total_over_3}*"
    )

    lines.append("")

    lines.append(
        "*Instruction:*"
    )

    lines.append(
        "All cases pending for more than 3 days "
        "shall be cleared immediately on priority."
    )

    return "\n".join(lines)


def make_sdn_message(
    sdn_name,
    division_name,
    report_date,
    row
):
    """
    Create individual S/DN WhatsApp message.
    """

    d03 = int(row["0-3"])
    d47 = int(row["4-7"])
    d815 = int(row["8-15"])
    d1630 = int(row["16-30"])
    d30 = int(row[">30"])

    total = (
        d03
        + d47
        + d815
        + d1630
        + d30
    )

    over_3 = (
        d47
        + d815
        + d1630
        + d30
    )

    message = f"""*PMSG INSPECTION PENDING*

*{sdn_name}*
{division_name}
Date: {report_date}

*Total Pending: {total}*
*>3 Days: {over_3}*

0-3 Days: {d03}
4-7 Days: {d47}
8-15 Days: {d815}
16-30 Days: {d1630}
>30 Days: {d30}

--------------------------------

*Instruction:*

All cases pending for more than 3 days
shall be cleared immediately on priority.

Please attend the pending inspection cases accordingly.
"""

    return message


# ============================================================
# EXCEL EXPORT
# ============================================================

def dataframe_to_excel(
    summary_df,
    detail_df,
    division_name,
    report_date
):
    """
    Create downloadable Excel workbook.
    """

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter"
    ) as writer:

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        summary_export = summary_df.copy()

        summary_export.to_excel(
            writer,
            sheet_name="S-DN Summary",
            index=False
        )

        # ----------------------------------------------------
        # Detailed data
        # ----------------------------------------------------

        detail_export = detail_df.copy()

        # Remove internal columns
        internal_columns = [
            "_Installation_Date",
            "_Circle",
            "_Division",
            "_SDN"
        ]

        detail_export = detail_export.drop(
            columns=[
                col
                for col in internal_columns
                if col in detail_export.columns
            ],
            errors="ignore"
        )

        detail_export.to_excel(
            writer,
            sheet_name="Pending Detail",
            index=False
        )

        # ----------------------------------------------------
        # Formatting
        # ----------------------------------------------------

        workbook = writer.book

        header_format = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter"
            }
        )

        cell_format = workbook.add_format(
            {
                "border": 1
            }
        )

        # Summary formatting
        summary_sheet = writer.sheets[
            "S-DN Summary"
        ]

        for col_num, value in enumerate(
            summary_export.columns
        ):
            summary_sheet.write(
                0,
                col_num,
                value,
                header_format
            )

        summary_sheet.freeze_panes(1, 0)

        # Set summary widths
        for idx, col in enumerate(
            summary_export.columns
        ):

            if col == "S/DN":
                width = 25

            else:
                width = 12

            summary_sheet.set_column(
                idx,
                idx,
                width,
                cell_format
            )

        # Detail formatting
        detail_sheet = writer.sheets[
            "Pending Detail"
        ]

        for col_num, value in enumerate(
            detail_export.columns
        ):
            detail_sheet.write(
                0,
                col_num,
                value,
                header_format
            )

        detail_sheet.freeze_panes(1, 0)

        for idx, col in enumerate(
            detail_export.columns
        ):

            if "Name" in str(col):
                width = 25

            elif "Address" in str(col):
                width = 35

            else:
                width = 18

            detail_sheet.set_column(
                idx,
                idx,
                width
            )

    output.seek(0)

    return output


# ============================================================
# APPLICATION TITLE
# ============================================================

st.title(
    "PMSG Inspection Pending Dashboard"
)

st.caption(
    "Upload the PMSG Inspection Pending Export "
    "and generate Circle / Division / S/DN-wise ageing reports."
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.sidebar.header(
    "Upload PMSG Export"
)

uploaded_file = st.sidebar.file_uploader(
    "Upload Inspection Pending Excel",
    type=["xlsx", "xls"],
    help=(
        "Upload the complete Inspection Pending "
        "export downloaded from the PMSG portal."
    )
)


# ============================================================
# INITIAL STATE
# ============================================================

if "processed_data" not in st.session_state:
    st.session_state.processed_data = None

if "column_mapping" not in st.session_state:
    st.session_state.column_mapping = None

if "file_name" not in st.session_state:
    st.session_state.file_name = None


# ============================================================
# PROCESS UPLOADED FILE
# ============================================================

if uploaded_file is not None:

    # Process only when new file is uploaded
    if (
        st.session_state.file_name
        != uploaded_file.name
    ):

        try:

            with st.spinner(
                "Reading PMSG Excel file..."
            ):

                raw_df = pd.read_excel(
                    uploaded_file
                )

                cleaned_df, mapping = clean_dataframe(
                    raw_df
                )

                st.session_state.processed_data = (
                    cleaned_df
                )

                st.session_state.column_mapping = (
                    mapping
                )

                st.session_state.file_name = (
                    uploaded_file.name
                )

            st.success(
                f"File loaded successfully: "
                f"{uploaded_file.name}"
            )

        except Exception as e:

            st.error(
                f"Error while reading the file: {e}"
            )

            st.stop()


# ============================================================
# STOP IF NO FILE
# ============================================================

if st.session_state.processed_data is None:

    st.info(
        "Please upload the PMSG Inspection Pending "
        "Excel export from the sidebar."
    )

    st.markdown(
        """
### Process

1. Download the complete Inspection Pending export from PMSG.
2. Upload the Excel file here.
3. Select Circle.
4. Select Division.
5. Select Report Date.
6. Click **Generate Report**.
7. Copy the WhatsApp message and send it to the Division group.
        """
    )

    st.stop()


# ============================================================
# DATA
# ============================================================

df = st.session_state.processed_data


# ============================================================
# FILE INFORMATION
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Uploaded Records",
        len(df)
    )

with col2:
    valid_installation = (
        df["_Installation_Date"]
        .notna()
        .sum()
    )

    st.metric(
        "Valid Installation Dates",
        int(valid_installation)
    )

with col3:
    st.metric(
        "Circles",
        df["_Circle"].nunique()
    )


# ============================================================
# FILTER SECTION
# ============================================================

st.sidebar.markdown("---")

st.sidebar.header(
    "Report Selection"
)

# ------------------------------------------------------------
# Circle
# ------------------------------------------------------------

circles = sorted(
    [
        x
        for x in df["_Circle"].unique()
        if str(x).strip() != ""
    ]
)

if not circles:

    st.error(
        "No Circle data found in uploaded file."
    )

    st.stop()

selected_circle = st.sidebar.selectbox(
    "Select Circle",
    circles
)


# ------------------------------------------------------------
# Division
# ------------------------------------------------------------

division_data = df[
    df["_Circle"] == selected_circle
]

divisions = sorted(
    [
        x
        for x in division_data["_Division"].unique()
        if str(x).strip() != ""
    ]
)

if not divisions:

    st.error(
        "No Division data found for selected Circle."
    )

    st.stop()

selected_division = st.sidebar.selectbox(
    "Select Division",
    divisions
)


# ------------------------------------------------------------
# Report Date
# ------------------------------------------------------------

report_date = st.sidebar.date_input(
    "Report Date",
    value=date.today()
)


# ============================================================
# GENERATE REPORT
# ============================================================

generate_report = st.sidebar.button(
    "Generate Report",
    type="primary",
    use_container_width=True
)


# ============================================================
# REPORT
# ============================================================

if generate_report:

    # --------------------------------------------------------
    # Filter Circle + Division
    # --------------------------------------------------------

    division_df = df[
        (df["_Circle"] == selected_circle)
        &
        (df["_Division"] == selected_division)
    ].copy()

    # --------------------------------------------------------
    # Calculate ageing
    # --------------------------------------------------------

    division_df = calculate_ageing(
        division_df,
        report_date
    )

    # --------------------------------------------------------
    # Create summary
    # --------------------------------------------------------

    summary_df = create_summary(
        division_df
    )

    # Save in session state
    st.session_state.report_data = division_df
    st.session_state.summary_data = summary_df
    st.session_state.report_date = report_date
    st.session_state.report_division = selected_division
    st.session_state.report_circle = selected_circle


# ============================================================
# DISPLAY REPORT IF GENERATED
# ============================================================

if "report_data" not in st.session_state:

    st.info(
        "Select Circle, Division and Report Date, "
        "then click **Generate Report**."
    )

    st.stop()


division_df = st.session_state.report_data
summary_df = st.session_state.summary_data
report_date = st.session_state.report_date
selected_division = st.session_state.report_division
selected_circle = st.session_state.report_circle


# ============================================================
# REPORT HEADER
# ============================================================

st.markdown("---")

st.subheader(
    f"{selected_division} - Inspection Pending"
)

st.write(
    f"Circle: **{selected_circle}**  \n"
    f"Report Date: **{report_date.strftime('%d-%m-%Y')}**"
)


# ============================================================
# DIVISION TOTAL METRICS
# ============================================================

totals = create_division_total(
    summary_df
)

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)

with m1:
    st.metric(
        "Total",
        totals["Total"]
    )

with m2:
    st.metric(
        "0-3 Days",
        totals["0-3"]
    )

with m3:
    st.metric(
        "4-7 Days",
        totals["4-7"]
    )

with m4:
    st.metric(
        "8-15 Days",
        totals["8-15"]
    )

with m5:
    st.metric(
        "16-30 Days",
        totals["16-30"]
    )

with m6:
    st.metric(
        ">30 Days",
        totals[">30"]
    )

with m7:
    st.metric(
        ">3 Days",
        totals[">3 Days"]
    )


# ============================================================
# S/DN SUMMARY
# ============================================================

st.markdown("---")

st.subheader(
    "S/DN-wise Ageing Summary"
)

display_summary = summary_df.copy()

st.dataframe(
    display_summary,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DETAILED S/DN LIST
# ============================================================

st.markdown("---")

st.subheader(
    "S/DN-wise Pending Details"
)

sdn_list = sorted(
    [
        x
        for x in division_df["_SDN"].unique()
        if str(x).strip() != ""
    ]
)

if sdn_list:

    selected_sdn = st.selectbox(
        "Select S/DN",
        sdn_list
    )

    sdn_df = division_df[
        division_df["_SDN"] == selected_sdn
    ].copy()

    # --------------------------------------------------------
    # S/DN metrics
    # --------------------------------------------------------

    sdn_summary = create_summary(
        sdn_df
    )

    if not sdn_summary.empty:

        sdn_row = sdn_summary.iloc[0]

        s1, s2, s3, s4, s5, s6, s7 = st.columns(7)

        with s1:
            st.metric(
                "Total",
                int(sdn_row["Total"])
            )

        with s2:
            st.metric(
                "0-3",
                int(sdn_row["0-3"])
            )

        with s3:
            st.metric(
                "4-7",
                int(sdn_row["4-7"])
            )

        with s4:
            st.metric(
                "8-15",
                int(sdn_row["8-15"])
            )

        with s5:
            st.metric(
                "16-30",
                int(sdn_row["16-30"])
            )

        with s6:
            st.metric(
                ">30",
                int(sdn_row[">30"])
            )

        with s7:
            st.metric(
                ">3 Days",
                int(sdn_row[">3 Days"])
            )

    # --------------------------------------------------------
    # S/DN detail data
    # --------------------------------------------------------

    sdn_display = sdn_df.copy()

    sdn_display = sdn_display.drop(
        columns=[
            "_Installation_Date",
            "_Circle",
            "_Division",
            "_SDN"
        ],
        errors="ignore"
    )

    st.dataframe(
        sdn_display,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# WHATSAPP SECTION
# ============================================================

st.markdown("---")

st.header(
    "WhatsApp Messages"
)


# ============================================================
# DIVISION WHATSAPP MESSAGE
# ============================================================

st.subheader(
    "Division WhatsApp Message"
)

division_message = make_division_message(
    summary_df,
    selected_division,
    report_date.strftime("%d-%m-%Y")
)

st.text_area(
    "Copy this message for Division WhatsApp Group",
    value=division_message,
    height=500
)


# ============================================================
# INDIVIDUAL S/DN WHATSAPP MESSAGE
# ============================================================

st.subheader(
    "Individual S/DN WhatsApp Message"
)

if not summary_df.empty:

    selected_message_sdn = st.selectbox(
        "Select S/DN for WhatsApp message",
        summary_df["S/DN"].tolist(),
        key="whatsapp_sdn"
    )

    selected_row = summary_df[
        summary_df["S/DN"]
        == selected_message_sdn
    ].iloc[0]

    sdn_message = make_sdn_message(
        selected_message_sdn,
        selected_division,
        report_date.strftime("%d-%m-%Y"),
        selected_row
    )

    st.text_area(
        "Copy this message for S/DN staff",
        value=sdn_message,
        height=400,
        key="sdn_whatsapp_message"
    )


# ============================================================
# EXCEL DOWNLOAD
# ============================================================

st.markdown("---")

st.subheader(
    "Download Report"
)

excel_file = dataframe_to_excel(
    summary_df,
    division_df,
    selected_division,
    report_date
)

file_name = (
    f"PMSG_Inspection_Pending_"
    f"{selected_division.replace('/', '-')}_"
    f"{report_date.strftime('%d-%m-%Y')}.xlsx"
)

st.download_button(
    label="Download Consolidated Excel",
    data=excel_file,
    file_name=file_name,
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    use_container_width=True
)


# ============================================================
# COLUMN INFORMATION
# ============================================================

st.markdown("---")

with st.expander(
    "Detected PMSG Export Columns"
):

    mapping = (
        st.session_state.column_mapping
    )

    mapping_df = pd.DataFrame(
        [
            {
                "Required Field": key,
                "Detected Column": (
                    value
                    if value is not None
                    else "Not Found"
                )
            }
            for key, value in mapping.items()
        ]
    )

    st.dataframe(
        mapping_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "PMSG Inspection Pending Dashboard | "
    "MGVCL"
)

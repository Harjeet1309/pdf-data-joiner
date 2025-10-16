import streamlit as st
import pandas as pd
import pdfplumber
from fuzzywuzzy import fuzz
from io import BytesIO

st.set_page_config(page_title="Universal File Data Joiner", layout="wide")
st.title("📂 Universal File Data Joiner")
st.write("Upload any two files (PDF, CSV, Excel, or TXT) — I'll automatically detect and join or compare them!")

uploaded_file1 = st.file_uploader("Upload First File", type=["pdf", "csv", "xlsx", "xls", "txt"])
uploaded_file2 = st.file_uploader("Upload Second File", type=["pdf", "csv", "xlsx", "xls", "txt"])

join_type = st.selectbox("Join type (when tables found)", ["inner", "left", "right", "outer"])

# ===== Extraction Functions =====
def extract_from_file(file):
    """Auto-detect file type and extract table or text."""
    name = file.name.lower()
    if name.endswith(".pdf"):
        df = extract_tables_pdfplumber(file)
        if df is not None:
            return df, None
        else:
            return None, extract_text_clean(file)
    elif name.endswith(".csv"):
        return pd.read_csv(file), None
    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file), None
    elif name.endswith(".txt"):
        lines = [line.strip() for line in file.getvalue().decode("utf-8", errors="ignore").splitlines() if line.strip()]
        return None, lines
    else:
        st.warning(f"Unsupported file format: {name}")
        return None, None

def extract_tables_pdfplumber(file):
    try:
        tables = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    tables.append(df)
        if tables:
            return pd.concat(tables, ignore_index=True)
    except Exception as e:
        st.warning(f"Table extraction error: {e}")
    return None

def extract_text_clean(file):
    lines = []
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    for ln in txt.splitlines():
                        ln = ln.strip()
                        if ln:
                            lines.append(ln)
    except Exception as e:
        st.warning(f"Text extraction error: {e}")
    return lines

def find_common_text(text1, text2, threshold=85):
    common = []
    for t1 in text1:
        for t2 in text2:
            if fuzz.token_set_ratio(t1, t2) >= threshold:
                common.append(t1)
                break
    # preserve uniqueness
    seen, uniq = set(), []
    for x in common:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq

# ===== Core Logic =====
if uploaded_file1 and uploaded_file2:
    with st.spinner("🔍 Extracting and processing..."):
        df1, text1 = extract_from_file(uploaded_file1)
        df2, text2 = extract_from_file(uploaded_file2)

        # If both have tables
        if df1 is not None and df2 is not None:
            st.success("✅ Found structured data in both files. Performing automatic join...")

            join_cols = []
            for col1 in df1.columns:
                for col2 in df2.columns:
                    try:
                        score = fuzz.ratio(str(col1).lower(), str(col2).lower())
                    except:
                        score = 0
                    if score > 80:
                        join_cols.append((col1, col2, score))

            if join_cols:
                join_cols = sorted(join_cols, key=lambda x: x[2], reverse=True)
                col1, col2, _ = join_cols[0]
                st.write(f"Joining on columns: **{col1}** ↔ **{col2}**")
                common = pd.merge(df1, df2, left_on=col1, right_on=col2, how=join_type)

                if common.empty:
                    st.info("Join produced no rows. Try a different join type.")
                else:
                    st.dataframe(common)
                    csv = common.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Download Joined Data as CSV", csv, "joined_data.csv", "text/csv")
            else:
                st.warning("No similar column names found to join automatically.")
                st.write("File 1 Columns:", list(df1.columns))
                st.write("File 2 Columns:", list(df2.columns))

        # If text-based comparison
        else:
            if text1 and text2:
                st.info("🧾 Comparing text content...")
                common_text = find_common_text(text1, text2)
                if common_text:
                    st.success(f"✅ Found {len(common_text)} common lines!")
                    st.table(pd.DataFrame({"Common Lines": common_text}))
                    csv = "\n".join(common_text).encode("utf-8")
                    st.download_button("⬇️ Download Common Text as CSV", csv, "common_text.csv", "text/csv")
                else:
                    st.error("❌ No common text found.")
            else:
                st.error("⚠️ Could not detect any structured or textual data in one or both files.")

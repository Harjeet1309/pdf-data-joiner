import streamlit as st
import pandas as pd
import pdfplumber
from fuzzywuzzy import fuzz
from io import BytesIO

st.set_page_config(page_title="PDF Data Joiner", layout="wide")
st.title("📄 PDF Data Joiner")
st.write("Upload two PDFs — I’ll find the common data or text automatically!")

uploaded_file1 = st.file_uploader("Upload First PDF", type=["pdf"])
uploaded_file2 = st.file_uploader("Upload Second PDF", type=["pdf"])

join_type = st.selectbox("Join type (when tables found)", ["inner", "left", "right", "outer"])

def extract_tables_pdfplumber(file):
    """
    Try to extract tables using pdfplumber's table detection.
    Returns a concatenated DataFrame or None if nothing found.
    """
    try:
        tables = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                # pdfplumber provides extract_table() or extract_tables()
                table = page.extract_table()  # returns list of rows (including header) or None
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    tables.append(df)
        if tables:
            return pd.concat(tables, ignore_index=True)
    except Exception as e:
        st.warning(f"Table extraction error: {e}")
    return None

def extract_text_clean(file):
    """
    Extract text lines reliably and handle None results.
    Returns list of cleaned lines (in order).
    """
    lines = []
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if not txt:
                    continue
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
    # preserve order and uniqueness
    seen = set()
    uniq = []
    for x in common:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq

if uploaded_file1 and uploaded_file2:
    with st.spinner("🔍 Extracting..."):
        # First try pdfplumber table extraction for both
        df1 = extract_tables_pdfplumber(uploaded_file1)
        df2 = extract_tables_pdfplumber(uploaded_file2)

        if df1 is not None and df2 is not None:
            st.success("✅ Found tables in both PDFs. Performing automatic join...")

            # Attempt auto column matching (fuzzy)
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
                # pick best match by highest score
                join_cols = sorted(join_cols, key=lambda x: x[2], reverse=True)
                col1, col2, _ = join_cols[0]
                common = pd.merge(df1, df2, left_on=col1, right_on=col2, how=join_type)
                if common.empty:
                    st.info("Join produced no rows. You may try a different join type.")
                else:
                    st.dataframe(common)
                    csv = common.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Download Common Data as CSV", csv, "common_data.csv", "text/csv")
            else:
                st.warning("No matching columns found to join automatically. Try manual column selection or check PDF table headers.")
                st.write("PDF1 columns:", list(df1.columns))
                st.write("PDF2 columns:", list(df2.columns))

        else:
            st.info("🧾 No tables found in one or both PDFs. Switching to text comparison mode...")
            text1 = extract_text_clean(uploaded_file1)
            text2 = extract_text_clean(uploaded_file2)

            # show counts so user knows what's happening
            st.write(f"Lines extracted — PDF1: {len(text1)}, PDF2: {len(text2)}")

            common_text = find_common_text(text1, text2)
            if common_text:
                st.success(f"✅ Found {len(common_text)} common lines!")
                # show as table for readability
                st.table(pd.DataFrame({"Common Lines": common_text}))
                # allow CSV download
                csv = "\n".join(common_text).encode("utf-8")
                st.download_button("⬇️ Download Common Text as CSV", csv, "common_text.csv", "text/csv")
            else:
                st.error("❌ No common text found.")

from flask import Flask, request, jsonify
import pandas as pd
import pdfplumber
import tabula
from fuzzywuzzy import fuzz
from io import BytesIO

app = Flask(__name__)

def extract_tables(file):
    try:
        tables = tabula.read_pdf(file, pages="all", multiple_tables=True)
        if tables and len(tables) > 0:
            df = pd.concat(tables, ignore_index=True)
            return df
    except:
        return None
    return None

def extract_text(file):
    text_data = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text_data.extend(page.extract_text().split("\n"))
    return list(set(text_data))

def find_common_text(text1, text2):
    common = []
    for t1 in text1:
        for t2 in text2:
            if fuzz.token_set_ratio(t1, t2) > 85:
                common.append(t1)
                break
    return list(set(common))

@app.route("/join", methods=["POST"])
def join_pdfs():
    f1 = request.files["pdf1"]
    f2 = request.files["pdf2"]
    df1 = extract_tables(f1)
    df2 = extract_tables(f2)

    if df1 is not None and df2 is not None:
        join_cols = []
        for col1 in df1.columns:
            for col2 in df2.columns:
                if fuzz.ratio(col1.lower(), col2.lower()) > 80:
                    join_cols.append((col1, col2))
        if join_cols:
            col1, col2 = join_cols[0]
            common = pd.merge(df1, df2, left_on=col1, right_on=col2, how="inner")
            return common.to_json(orient="records")
        return jsonify({"message": "No matching columns found."})
    else:
        text1 = extract_text(f1)
        text2 = extract_text(f2)
        common_text = find_common_text(text1, text2)
        return jsonify({"common_text": common_text})

if __name__ == "__main__":
    app.run(debug=True)

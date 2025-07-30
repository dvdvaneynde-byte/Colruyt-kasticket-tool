import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

st.set_page_config(page_title="Colruyt Ticket naar Excel", layout="centered")
st.title("🧾 Colruyt kasticket naar Excel")

uploaded_file = st.file_uploader("Upload een Colruyt-kasticket (PDF)", type=["pdf"])


def parse_ticket(text):
    lines = text.split('\n')
    data = []
    date = ""
    winkel = ""

    # Zoek datum en winkel (simpele heuristiek)
    for line in lines:
        if re.search(r"\d{2}/\d{2}/\d{4}", line):
            date_match = re.search(r"\d{2}/\d{2}/\d{4}", line)
            if date_match:
                date = date_match.group()
        if "CADI" in line or "Colruyt" in line:
            winkel = line.strip()

    # Zoek producten
    pattern = re.compile(r"(.+?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)$")
    for line in lines:
        match = pattern.search(line)
        if match:
            product = match.group(1).strip()
            aantal = match.group(2).replace(',', '.')
            totaal = match.group(3).replace(',', '.')
            try:
                aantal_f = float(aantal)
                totaal_f = float(totaal)
                eenheidsprijs = round(totaal_f / aantal_f, 2) if aantal_f != 0 else 0
                data.append({
                    "Datum": date,
                    "Winkel": winkel,
                    "Product": product,
                    "Aantal": aantal_f,
                    "Eenheidsprijs": eenheidsprijs,
                    "Totaalprijs": totaal_f
                })
            except:
                continue

    return pd.DataFrame(data)


if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        all_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"

    df = parse_ticket(all_text)

    if not df.empty:
        st.success("✅ Gegevens herkend! Bekijk of alles klopt.")
        st.dataframe(df)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Aankopen")
        st.download_button(
            label="💾 Download Excel-bestand",
            data=output.getvalue(),
            file_name="colruyt_aankopen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ Geen producten gevonden in dit ticket.")

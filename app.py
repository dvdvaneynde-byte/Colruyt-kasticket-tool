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

    # Zoek producten met exacte benaming en hoeveelheid uit ticket
    pattern = re.compile(r"(.+?)\s+(\S+)\s+(\d+[.,]?\d*)\s+(\d+[.,]?\d*)$")
    for line in lines:
        match = pattern.search(line)
        if match:
            benaming = match.group(1).strip()
            hoeveelheid = match.group(2).strip()
            eenheidsprijs = match.group(3).replace(",", ".")
            totaal = match.group(4).replace(",", ".")
            try:
                eenheidsprijs_f = float(eenheidsprijs)
                totaal_f = float(totaal)
                data.append({
                    "Benaming": benaming,
                    "Hoeveelheid": hoeveelheid,
                    "Eenheidsprijs": eenheidsprijs_f,
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

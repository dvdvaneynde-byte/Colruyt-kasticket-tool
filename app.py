import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Colruyt Ticket naar Excel", layout="centered")
st.title("🧾 Colruyt kasticket naar Excel")

uploaded_files = st.file_uploader("Upload één of meerdere Colruyt-kastickets (PDF)", type=["pdf"], accept_multiple_files=True)


def parse_ticket(text):
    lines = text.split('\n')
    data = []
    aankoopdatum = ""

    # Zoek aankoopdatum
    for line in lines:
        match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
        if match:
            try:
                aankoopdatum = datetime.strptime(match.group(1), "%d/%m/%Y").date()
                break
            except:
                continue

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
                eenheidsprijs_f = f"€{float(eenheidsprijs):.2f}"
                totaal_f_val = float(totaal)
                totaal_f = f"€{totaal_f_val:.2f}"
                data.append({
                    "Datum": aankoopdatum,
                    "Benaming": benaming,
                    "Hoeveelheid": hoeveelheid,
                    "Eenheidsprijs": eenheidsprijs_f,
                    "Totaalprijs": totaal_f,
                    "TotaalNum": totaal_f_val
                })
            except:
                continue

    return pd.DataFrame(data)


if uploaded_files:
    all_dataframes = []

    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"

        df = parse_ticket(all_text)
        if not df.empty:
            all_dataframes.append(df)

    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)
        final_df['Datum'] = pd.to_datetime(final_df['Datum'])
        final_df['Jaar'] = final_df['Datum'].dt.year
        final_df['Maand'] = final_df['Datum'].dt.to_period('M').astype(str)

        st.success("✅ Gegevens uit alle tickets herkend! Bekijk of alles klopt.")
        st.dataframe(final_df.drop(columns=["TotaalNum"]))

        # Tellingen per maand en jaar o.b.v. Hoeveelheid als tekstwaarde
        pivot_maand = final_df.groupby(['Maand', 'Benaming', 'Hoeveelheid']).size().reset_index(name='Aantal lijnen')
        pivot_maand_totalen = final_df.groupby(['Maand', 'Benaming'])['TotaalNum'].sum().reset_index()
        pivot_maand_totalen['Totaalprijs'] = pivot_maand_totalen['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        pivot_maand = pd.merge(pivot_maand, pivot_maand_totalen.drop(columns='TotaalNum'), on=['Maand', 'Benaming'])

        pivot_jaar = final_df.groupby(['Jaar', 'Benaming', 'Hoeveelheid']).size().reset_index(name='Aantal lijnen')
        pivot_jaar_totalen = final_df.groupby(['Jaar', 'Benaming'])['TotaalNum'].sum().reset_index()
        pivot_jaar_totalen['Totaalprijs'] = pivot_jaar_totalen['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        pivot_jaar = pd.merge(pivot_jaar, pivot_jaar_totalen.drop(columns='TotaalNum'), on=['Jaar', 'Benaming'])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.drop(columns=["TotaalNum"]).to_excel(writer, index=False, sheet_name="Aankopen")
            pivot_maand.to_excel(writer, index=False, sheet_name="Totaal per maand")
            pivot_jaar.to_excel(writer, index=False, sheet_name="Totaal per jaar")

        st.download_button(
            label="💾 Download Excel-bestand",
            data=output.getvalue(),
            file_name="colruyt_aankopen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ Geen producten gevonden in de geüploade tickets.")

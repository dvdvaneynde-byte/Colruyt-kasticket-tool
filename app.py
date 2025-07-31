import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Colruyt Ticket naar Excel", layout="centered")
st.title("🧾 Colruyt kasticket naar Excel")

uploaded_files = st.file_uploader("Upload één of meerdere Colruyt-kastickets als PDF-bestand", type=["pdf"], accept_multiple_files=True)

def parse_ticket(text, filename):
    lines = text.split('\n')
    data = []
    aankoopdatum = ""

    # Zoek aankoopdatum
    for line in lines:
        match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", line)
        if match:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
                try:
                    aankoopdatum = datetime.strptime(match.group(1), fmt).date()
                    break
                except:
                    continue
            if aankoopdatum:
                break

    pattern = re.compile(r"(.+?)\s+(\S+)\s+(\d+[.,]?\d*)\s+(\d+[.,]?\d*)$")
    for line in lines:
        match = pattern.search(line)
        if match:
            benaming_raw = match.group(1).strip()
            benaming = re.sub(r"^(?:[A-Z]\s*)?\d{3,6}\s+", "", benaming_raw).strip()
            hoeveelheid = match.group(2).strip()
            eenheidsprijs = match.group(3).replace(",", ".")
            totaal = match.group(4).replace(",", ".")

            if len(benaming) < 3:
                continue
            uitsluit_woorden = ["colruyt", "retail", "prijs gezien", "bel ons", "toch ergens"]
            if any(w in benaming.lower() for w in uitsluit_woorden):
                continue
            if not re.match(r"^\d+([.,]\d+)?\s*(g|kg|ml|l|cl)?$", hoeveelheid.lower()):
                continue

            try:
                eenheidsprijs_f = f"€{float(eenheidsprijs):.2f}"
                totaal_f_val = float(totaal)
                totaal_f = f"€{totaal_f_val:.2f}"
                data.append({
                    "Ticket": filename,
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

def is_gewicht(hoeveelheid):
    return bool(re.search(r"\d+[.,]?\d*\s*(g|kg|ml|l|cl)", hoeveelheid.lower()))

def extract_gewicht_kg(hoeveelheid):
    match = re.search(r"(\d+[.,]?\d*)\s*(g|kg|ml|l|cl)", hoeveelheid.lower())
    if match:
        waarde = float(match.group(1).replace(",", "."))
        eenheid = match.group(2)
        if eenheid == "kg" or eenheid == "l":
            return waarde
        elif eenheid == "g" or eenheid == "ml":
            return waarde / 1000
        elif eenheid == "cl":
            return waarde / 100
    return 0

def aantal_stuks_uit_hoeveelheid(hoeveelheid):
    try:
        clean = re.sub(r"[^\d,\.]", "", hoeveelheid)
        clean = clean.replace(",", ".")
        return float(clean)
    except:
        return 1

def auto_adjust_column_widths(writer, df, sheet_name):
    worksheet = writer.sheets[sheet_name]
    for i, col in enumerate(df.columns):
        max_len = max(
            df[col].astype(str).map(len).max(),
            len(col)
        ) + 2
        worksheet.set_column(i, i, max_len)

if uploaded_files:
    all_dataframes = []

    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"

        df = parse_ticket(all_text, uploaded_file.name)
        if not df.empty:
            all_dataframes.append(df)

    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)
        final_df['Datum'] = pd.to_datetime(final_df['Datum'])
        final_df['Jaar'] = final_df['Datum'].dt.year
        final_df['Maand'] = final_df['Datum'].dt.to_period('M').astype(str)

        final_df['IsGewicht'] = final_df['Hoeveelheid'].apply(is_gewicht)
        final_df['GewichtKg'] = final_df.apply(lambda row: extract_gewicht_kg(row['Hoeveelheid']) if row['IsGewicht'] else 0, axis=1)

        final_df['AantalStuks'] = final_df.apply(
            lambda row: 0 if row['IsGewicht'] else aantal_stuks_uit_hoeveelheid(row['Hoeveelheid']),
            axis=1
        )

        st.success("✅ Gegevens uit alle tickets herkend! Bekijk of alles klopt.")
        st.dataframe(final_df.drop(columns=["TotaalNum", "IsGewicht"]))

        # Samenvatting per maand (prijs als laatste kolom)
        pivot_maand = final_df.groupby(['Maand', 'Benaming']).agg({
            'TotaalNum': 'sum',
            'GewichtKg': 'sum',
            'AantalStuks': 'sum'
        }).reset_index()
        pivot_maand['Totaal aantal (stuks)'] = pivot_maand['AantalStuks'].astype(int)
        pivot_maand['Totaal gewicht (kg)'] = pivot_maand['GewichtKg'].apply(lambda x: f"{x:.2f} kg")
        pivot_maand['Totaalprijs'] = pivot_maand['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        pivot_maand = pivot_maand[['Maand', 'Benaming', 'Totaal aantal (stuks)', 'Totaal gewicht (kg)', 'Totaalprijs']]

        # Samenvatting per jaar (prijs als laatste kolom)
        pivot_jaar = final_df.groupby(['Jaar', 'Benaming']).agg({
            'TotaalNum': 'sum',
            'GewichtKg': 'sum',
            'AantalStuks': 'sum'
        }).reset_index()
        pivot_jaar['Totaal aantal (stuks)'] = pivot_jaar['AantalStuks'].astype(int)
        pivot_jaar['Totaal gewicht (kg)'] = pivot_jaar['GewichtKg'].apply(lambda x: f"{x:.2f} kg")
        pivot_jaar['Totaalprijs'] = pivot_jaar['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        pivot_jaar = pivot_jaar[['Jaar', 'Benaming', 'Totaal aantal (stuks)', 'Totaal gewicht (kg)', 'Totaalprijs']]

        # Totaalprijs per ticket
        totaal_per_ticket = final_df.groupby('Ticket')['TotaalNum'].sum().reset_index()
        totaal_per_ticket['Totaalprijs'] = totaal_per_ticket['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        st.subheader("💰 Totaalprijs per ticket")
        st.dataframe(totaal_per_ticket[['Ticket', 'Totaalprijs']])

        # Totaalprijs per maand
        totaal_per_maand = final_df.groupby('Maand')['TotaalNum'].sum().reset_index()
        totaal_per_maand['Totaalprijs'] = totaal_per_maand['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        st.subheader("💰 Totaalprijs per maand")
        st.dataframe(totaal_per_maand[['Maand', 'Totaalprijs']])

        # Totaalprijs per jaar
        totaal_per_jaar = final_df.groupby('Jaar')['TotaalNum'].sum().reset_index()
        totaal_per_jaar['Totaalprijs'] = totaal_per_jaar['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        st.subheader("💰 Totaalprijs per jaar")
        st.dataframe(totaal_per_jaar[['Jaar', 'Totaalprijs']])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for ticket_name in final_df['Ticket'].unique():
                ticket_df = final_df[final_df['Ticket'] == ticket_name].drop(columns=["TotaalNum", "GewichtKg", "AantalStuks", "IsGewicht"])
                sheet_name = ticket_name[:31]  # Excel sheet name limit
                ticket_df.to_excel(writer, index=False, sheet_name=sheet_name)
                auto_adjust_column_widths(writer, ticket_df, sheet_name)

            # Schrijven en auto kolombreedte voor samenvattingen
            for df, sheet_name in [(pivot_maand, "Totaal per maand"), (pivot_jaar, "Totaal per jaar")]:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
                auto_adjust_column_widths(writer, df, sheet_name)

            # Schrijven totaalprijzen
            for df, sheet_name in [(totaal_per_ticket, "Totaal per ticket"),
                                   (totaal_per_maand, "Totaalprijs per maand"),
                                   (totaal_per_jaar, "Totaalprijs per jaar")]:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
                auto_adjust_column_widths(writer, df, sheet_name)

        st.download_button(
            label="💾 Download Excel-bestand",
            data=output.getvalue(),
            file_name="colruyt_aankopen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ Geen producten gevonden in de geüploade tickets.")

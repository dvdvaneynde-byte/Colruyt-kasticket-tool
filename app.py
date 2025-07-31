import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Colruyt Ticket naar Excel", layout="centered")
st.title("🧾 Colruyt kasticket naar Excel")

# Maak uploader groter en duidelijker
uploaded_files = st.file_uploader(
    "**Upload één of meerdere Colruyt-kastickets (PDF)**",
    type=["pdf"], accept_multiple_files=True,
    help="Selecteer één of meerdere PDF-bestanden van je Colruyt-kasticket"
)

def parse_ticket(text, filename):
    lines = text.split('\n')
    data = []
    aankoopdatum = None

    # Verbeterde datumextractie:
    # Zoek de eerste datum in het formaat dd/mm/yyyy, maar alleen bovenaan het ticket (eerste 20 regels)
    for line in lines[:20]:
        match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
        if match:
            try:
                aankoopdatum = datetime.strptime(match.group(1), "%d/%m/%Y").date()
                break
            except:
                continue

    # Als nog geen datum, zoek in hele tekst (fallback)
    if aankoopdatum is None:
        for line in lines:
            match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
            if match:
                try:
                    aankoopdatum = datetime.strptime(match.group(1), "%d/%m/%Y").date()
                    break
                except:
                    continue

    # Betere regex voor productregels:
    # Colruyt tickets hebben vaak een patroon:
    # productnaam [spaties] hoeveelheid [spaties] prijs per eenheid [spaties] totaalprijs
    # Hoeveelheid kan iets zijn als '1', '2', '0.5 kg', '500 g', '3 st'
    # Regex: productnaam (alles tot vóór de hoeveelheid), hoeveelheid, eenheidsprijs, totaalprijs

    pattern = re.compile(
        r"^(.*?)\s{2,}(\d+[.,]?\d*\s*(?:kg|g|l|ml|cl|st)?)\s+(\d+[.,]?\d*)\s+(\d+[.,]?\d*)$",
        re.IGNORECASE
    )

    for line in lines:
        match = pattern.search(line.strip())
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
        if eenheid in ["kg", "l"]:
            return waarde
        elif eenheid in ["g", "ml"]:
            return waarde / 1000
        elif eenheid == "cl":
            return waarde / 100
    return None


def extract_aantal_stuks(hoeveelheid):
    # Haal aantal stuks eruit als alleen een getal staat of getal + 'st'
    match = re.match(r"^(\d+)(?:\s*st)?$", hoeveelheid.strip().lower())
    if match:
        return int(match.group(1))
    return 1  # standaard 1 als geen expliciet getal


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
        final_df['GewichtKg'] = final_df.apply(lambda row: extract_gewicht_kg(row['Hoeveelheid']) if row['IsGewicht'] else None, axis=1)
        final_df['AantalStuks'] = final_df.apply(lambda row: extract_aantal_stuks(row['Hoeveelheid']) if not row['IsGewicht'] else 0, axis=1)

        st.success("✅ Gegevens uit alle tickets herkend! Bekijk of alles klopt.")
        st.dataframe(final_df.drop(columns=["TotaalNum", "IsGewicht"]))

        # Samenvatting per maand
        pivot_maand = final_df.groupby(['Maand', 'Benaming']).agg({
            'TotaalNum': 'sum',
            'GewichtKg': 'sum',
            'AantalStuks': 'sum'
        }).reset_index()
        pivot_maand['Totaalprijs'] = pivot_maand['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        pivot_maand['Totaal aantal (stuks)'] = pivot_maand['AantalStuks'].astype(int)
        pivot_maand['Totaal gewicht (kg)'] = pivot_maand['GewichtKg'].fillna(0).apply(lambda x: f"{x:.2f} kg")
        pivot_maand = pivot_maand[['Maand', 'Benaming', 'Totaalprijs', 'Totaal aantal (stuks)', 'Totaal gewicht (kg)']]

        # Samenvatting per jaar
        pivot_jaar = final_df.groupby(['Jaar', 'Benaming']).agg({
            'TotaalNum': 'sum',
            'GewichtKg': 'sum',
            'AantalStuks': 'sum'
        }).reset_index()
        pivot_jaar['Totaalprijs'] = pivot_jaar['TotaalNum'].apply(lambda x: f"€{x:.2f}")
        pivot_jaar['Totaal aantal (stuks)'] = pivot_jaar['AantalStuks'].astype(int)
        pivot_jaar['Totaal gewicht (kg)'] = pivot_jaar['GewichtKg'].fillna(0).apply(lambda x: f"{x:.2f} kg")
        pivot_jaar = pivot_jaar[['Jaar', 'Benaming', 'Totaalprijs', 'Totaal aantal (stuks)', 'Totaal gewicht (kg)']]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for ticket_name in final_df['Ticket'].unique():
                ticket_df = final_df[final_df['Ticket'] == ticket_name].drop(
                    columns=["TotaalNum", "GewichtKg", "AantalStuks", "IsGewicht"])
                sheet_name = ticket_name[:31]  # Excel sheet name limit
                ticket_df.to_excel(writer, index=False, sheet_name=sheet_name)

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
else:
    st.info("📄 Upload hier je Colruyt PDF-kastickets om te starten.")

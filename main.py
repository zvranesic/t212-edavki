import pandas as pd
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

# --- NASTAVITVE UPORABNIKA ---
TAX_YEAR = 2025
TAX_NUMBER = "45645645"
NAME = "Janez Novak"
ADDRESS = "Davčna ul. 1"
CITY = "Ljubljana"
POST_NUMBER = "1000"
POST_NAME = "Ljubljana"
EMAIL = "janez.novak@gmail.com"
PHONE = "031234567"

INPUT_FOLDER = './input'
RATE_FOLDER = './rate'
OUTPUT_FOLDER = './output'

# SPLIT LOGIKA (Nujno za NVDA, da zaloga v 2025 ne bo negativna)
STOCK_SPLITS = [
    ('US67066G1040', '2024-06-10', 10.0),  # NVDA split 1:10
]


def format_high_precision(val):
    """Formatira številko na visoko natančnost, odstrani odvečne ničle na koncu."""
    if val is None:
        return "0.0000"
    return f"{float(val):.8f}".rstrip('0').rstrip('.')


def create_edavki_xml():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # 1. Naložimo tečaje
    rate_files = [f for f in os.listdir(RATE_FOLDER) if f.endswith('.csv')]
    if not rate_files:
        print("Napaka: Manjka datoteka s tečaji v mapi /rate!")
        return
    rates_df = pd.read_csv(os.path.join(RATE_FOLDER, rate_files[0]))
    rates_df['Date'] = pd.to_datetime(rates_df['Date'])
    rates_df = rates_df.sort_values('Date')

    # 2. Branje datotek iz /input
    csv_files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.csv')]
    if not csv_files:
        print("Napaka: Ni CSV datotek v mapi /input!")
        return

    needed_cols = ['Action', 'Time', 'ISIN', 'Ticker', 'Name',
                   'No. of shares', 'Price / share', 'Currency (Price / share)']
    all_dfs = []

    for file in csv_files:
        path = os.path.join(INPUT_FOLDER, file)
        temp_df = pd.read_csv(path)
        existing_cols = [c for c in needed_cols if c in temp_df.columns]
        temp_df = temp_df[existing_cols]
        all_dfs.append(temp_df)

    df = pd.concat(all_dfs, ignore_index=True)

    # 3. STROGA DEDUPLIKACIJA (Popravljeno 's' za preprečitev FutureWarning)
    df['Time'] = pd.to_datetime(df['Time']).dt.floor('s')
    df = df.drop_duplicates(
        subset=['Time', 'Action', 'ISIN', 'No. of shares', 'Price / share'])
    df = df.sort_values('Time')
    df = df[df['Action'].str.contains('buy|sell', case=False, na=False)]

    # 4. STOCK SPLITS (NVDA popravek brez zaokroževanja)
    for isin, split_date, ratio in STOCK_SPLITS:
        split_dt = pd.to_datetime(split_date)
        mask = (df['ISIN'] == isin) & (df['Time'] < split_dt)
        df.loc[mask, 'No. of shares'] = df.loc[mask, 'No. of shares'] * ratio
        df.loc[mask, 'Price / share'] = df.loc[mask, 'Price / share'] / ratio

    df['Date_only'] = df['Time'].dt.normalize()

    # 5. Združevanje s tečaji in preračun v EUR
    df = pd.merge_asof(df, rates_df, left_on='Date_only',
                       right_on='Date', direction='backward')

    def to_eur(row):
        if row['Currency (Price / share)'] == 'EUR':
            return float(row['Price / share'])
        return float(row['Price / share']) * float(row['Price'])

    df['Price_EUR'] = df.apply(to_eur, axis=1)
    df['Date_Str'] = df['Time'].dt.strftime('%Y-%m-%d')
    df['Year_val'] = df['Time'].dt.year

    # 6. XML Gradnja (V9)
    NS_EDP = "http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd"
    NS_MAIN = "http://edavki.durs.si/Documents/Schemas/Doh_KDVP_9.xsd"
    ET.register_namespace('edp', NS_EDP)
    ET.register_namespace('', NS_MAIN)

    root = ET.Element(f"{{{NS_MAIN}}}Envelope")
    header = ET.SubElement(root, f"{{{NS_EDP}}}Header")
    taxpayer = ET.SubElement(header, f"{{{NS_EDP}}}taxpayer")
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}taxNumber").text = TAX_NUMBER
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}taxpayerType").text = "FO"
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}name").text = NAME
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}address1").text = ADDRESS
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}city").text = CITY
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}postNumber").text = POST_NUMBER
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}postName").text = POST_NAME
    ET.SubElement(root, f"{{{NS_EDP}}}AttachmentList")
    ET.SubElement(root, f"{{{NS_EDP}}}Signatures")

    body = ET.SubElement(root, f"{{{NS_MAIN}}}body")
    ET.SubElement(body, f"{{{NS_EDP}}}bodyContent")
    doh_kdvp = ET.SubElement(body, f"{{{NS_MAIN}}}Doh_KDVP")

    isins_sold = df[(df['Action'].str.contains('sell', case=False)) & (
        df['Year_val'] == TAX_YEAR)]['ISIN'].unique()

    kdvp = ET.SubElement(doh_kdvp, f"{{{NS_MAIN}}}KDVP")
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}DocumentWorkflowID").text = "O"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}Year").text = str(TAX_YEAR)
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}PeriodStart").text = f"{TAX_YEAR}-01-01"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}PeriodEnd").text = f"{TAX_YEAR}-12-31"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}IsResident").text = "true"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}TelephoneNumber").text = PHONE
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}SecurityCount").text = str(
        len(isins_sold))
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}SecurityShortCount").text = "0"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}SecurityWithContractCount").text = "0"
    ET.SubElement(
        kdvp, f"{{{NS_MAIN}}}SecurityWithContractShortCount").text = "0"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}ShareCount").text = "0"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}Email").text = EMAIL

    for isin in isins_sold:
        group = df[df['ISIN'] == isin].copy()
        group = group[group['Time'] <= f"{TAX_YEAR}-12-31 23:59:59"]

        ticker = group['Ticker'].iloc[0]
        kdvp_item = ET.SubElement(doh_kdvp, f"{{{NS_MAIN}}}KDVPItem")
        ET.SubElement(
            kdvp_item, f"{{{NS_MAIN}}}InventoryListType").text = "PLVP"
        ET.SubElement(
            kdvp_item, f"{{{NS_MAIN}}}Name").text = f"{ticker} | {isin}"
        ET.SubElement(kdvp_item, f"{{{NS_MAIN}}}HasForeignTax").text = "false"
        ET.SubElement(
            kdvp_item, f"{{{NS_MAIN}}}HasLossTransfer").text = "false"
        ET.SubElement(
            kdvp_item, f"{{{NS_MAIN}}}ForeignTransfer").text = "false"
        ET.SubElement(
            kdvp_item, f"{{{NS_MAIN}}}TaxDecreaseConformance").text = "false"

        securities = ET.SubElement(kdvp_item, f"{{{NS_MAIN}}}Securities")
        ET.SubElement(securities, f"{{{NS_MAIN}}}ISIN").text = str(isin)
        ET.SubElement(
            securities, f"{{{NS_MAIN}}}Name").text = f"{ticker} | {isin}"
        ET.SubElement(securities, f"{{{NS_MAIN}}}IsFond").text = "false"

        running_qty = 0.0
        row_id = 0
        for _, row in group.iterrows():
            qty = float(row['No. of shares'])
            is_buy = "buy" in row['Action'].lower()

            if is_buy:
                running_qty += qty
            else:
                running_qty -= qty

            if abs(running_qty) < 1e-9:
                running_qty = 0.0

            if not is_buy and row['Year_val'] != TAX_YEAR:
                continue

            xml_row = ET.SubElement(securities, f"{{{NS_MAIN}}}Row")
            ET.SubElement(xml_row, f"{{{NS_MAIN}}}ID").text = str(row_id)
            row_id += 1

            if is_buy:
                p = ET.SubElement(xml_row, f"{{{NS_MAIN}}}Purchase")
                ET.SubElement(p, f"{{{NS_MAIN}}}F1").text = row['Date_Str']
                ET.SubElement(p, f"{{{NS_MAIN}}}F2").text = "B"
                ET.SubElement(
                    p, f"{{{NS_MAIN}}}F3").text = format_high_precision(qty)
                ET.SubElement(p, f"{{{NS_MAIN}}}F4").text = format_high_precision(
                    row['Price_EUR'])
                ET.SubElement(p, f"{{{NS_MAIN}}}F5").text = "0.0000"
            else:
                s = ET.SubElement(xml_row, f"{{{NS_MAIN}}}Sale")
                ET.SubElement(s, f"{{{NS_MAIN}}}F6").text = row['Date_Str']
                ET.SubElement(
                    s, f"{{{NS_MAIN}}}F7").text = format_high_precision(qty)
                ET.SubElement(s, f"{{{NS_MAIN}}}F9").text = format_high_precision(
                    row['Price_EUR'])

            ET.SubElement(xml_row, f"{{{NS_MAIN}}}F8").text = format_high_precision(
                running_qty)

    xml_str = ET.tostring(root, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="\t")
    final_xml = pretty_xml.replace('xmlns:default', 'xmlns')

    # --- LOGIKA ZA POIMENOVANJE DATOTEKE (da ne povozi obstoječe) ---
    base_name = f"Doh_KDVP_{TAX_YEAR}"
    extension = ".xml"
    filename = f"{base_name}{extension}"
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    counter = 1
    while os.path.exists(output_path):
        filename = f"{base_name}_v{counter}{extension}"
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        counter += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"KONČANO! Datoteka shranjena kot: {filename}")


if __name__ == "__main__":
    create_edavki_xml()

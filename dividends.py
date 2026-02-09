import pandas as pd
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sys

if sys.platform.startswith("win"):
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

try:
    import settings
except ImportError:
    print("Napaka: Datoteka settings.py ne obstaja!")
    exit()


def get_country_from_isin(isin):
    """Extract country code from ISIN"""
    if not isin or len(isin) < 2:
        return "US"

    country_code = isin[:2]
    # Map to full country codes used in tax forms
    country_map = {
        'US': 'US',  # United States
        'NL': 'NL',  # Netherlands
        'DE': 'DE',  # Germany
        'GB': 'GB',  # United Kingdom
        'IE': 'IE',  # Ireland
        'FR': 'FR',  # France
    }
    return country_map.get(country_code, country_code)


def create_dividend_xml(rates_df):
    """
    Generate Doh-Div XML for dividend tax reporting
    """
    if not os.path.exists(settings.OUTPUT_FOLDER):
        os.makedirs(settings.OUTPUT_FOLDER)

    # Load CSV files
    csv_files = [f for f in os.listdir(settings.INPUT_FOLDER) if f.endswith('.csv')]
    if not csv_files:
        print("Napaka: Ni datotek v mapi /input!")
        return

    all_dfs = []
    for file in csv_files:
        all_dfs.append(pd.read_csv(os.path.join(settings.INPUT_FOLDER, file)))

    df = pd.concat(all_dfs, ignore_index=True)
    df['Time'] = pd.to_datetime(df['Time']).dt.floor('s')
    df = df.drop_duplicates(subset=['Time', 'Action', 'ISIN', 'No. of shares', 'Price / share'])
    df = df.sort_values('Time')

    # Filter dividend transactions
    df_dividends = df[df['Action'].str.contains('Dividend', case=False, na=False)].copy()

    if len(df_dividends) == 0:
        print("\nNi dividend transakcij za poročanje.")
        return

    # Add year column
    df_dividends['Year'] = df_dividends['Time'].dt.year

    # Filter for tax year
    df_dividends = df_dividends[df_dividends['Year'] == settings.TAX_YEAR]

    if len(df_dividends) == 0:
        print(f"\nNi dividend transakcij za leto {settings.TAX_YEAR}.")
        return

    # Merge with ECB rates
    df_dividends['Date_only'] = df_dividends['Time'].dt.normalize()
    df_dividends = pd.merge_asof(
        df_dividends, rates_df, left_on='Date_only', right_on='Date', direction='backward')

    # Convert to EUR
    def to_eur(row):
        curr = row['Currency (Price / share)']
        val = float(row['Price / share'])
        if curr == 'EUR':
            return val
        if curr == 'USD':
            return val / row['USD']
        if curr == 'GBP':
            return val / row['GBP']
        if curr == 'GBX':
            return (val / 100) / row['GBP']
        return val

    def withholding_to_eur(row):
        """Convert withholding tax to EUR"""
        if pd.isna(row['Withholding tax']) or row['Withholding tax'] == 0:
            return 0.0

        curr = row['Currency (Withholding tax)']
        val = float(row['Withholding tax'])

        if curr == 'EUR':
            return val
        if curr == 'USD':
            return val / row['USD']
        if curr == 'GBP':
            return val / row['GBP']
        return val

    # Calculate dividend amounts in EUR
    df_dividends['DividendPerShare_EUR'] = df_dividends.apply(to_eur, axis=1)
    df_dividends['Withholding_EUR'] = df_dividends.apply(withholding_to_eur, axis=1)
    df_dividends['Gross_EUR'] = df_dividends['No. of shares'] * df_dividends['DividendPerShare_EUR']

    # Terminal output
    C_GREEN = "\033[92m"
    C_BOLD = "\033[1m"
    C_END = "\033[0m"

    print("\n" + "╔" + "═"*60 + "╗")
    print(f"║ {C_BOLD}POROČILO O DIVIDENDAH ZA LETO {settings.TAX_YEAR}{C_END:<30} ║")
    print("╠" + "═"*60 + "╣")

    total_gross = df_dividends['Gross_EUR'].sum()
    total_withholding = df_dividends['Withholding_EUR'].sum()
    total_net = total_gross - total_withholding

    slovenian_tax = total_gross * 0.275  # 27.5% Slovenia tax
    tax_credit = total_withholding
    final_tax = max(0, slovenian_tax - tax_credit)

    print(f"║ BRUTO DIVIDENDE:                    {C_GREEN}{total_gross:>15.2f} EUR{C_END} ║")
    print(f"║ TUJI DAVEK (USA 15%):               {total_withholding:>15.2f} EUR ║")
    print(f"║ NETO PREJETO:                       {total_net:>15.2f} EUR ║")
    print("╠" + "═"*60 + "╣")
    print(f"║ SLOVENSKI DAVEK (27.5%):           {slovenian_tax:>15.2f} EUR ║")
    print(f"║ MINUS: Tuji davek (kredit):        {tax_credit:>15.2f} EUR ║")
    print(f"║ ZA PLAČILO:                         {C_BOLD}{final_tax:>15.2f} EUR{C_END} ║")
    print("╚" + "═"*60 + "╝")

    print(f"\n📑 PREGLED DIVIDEND PO DELNICAH:")
    print(f"{'TICKER':<10} | {'DATUM':<12} | {'BRUTO':>12} | {'TUJI DAVEK':>12} | {'NETO':>12}")
    print("-" * 68)

    for _, row in df_dividends.iterrows():
        date_str = row['Time'].strftime('%Y-%m-%d')
        ticker = row['Ticker']
        gross = row['Gross_EUR']
        withh = row['Withholding_EUR']
        net = gross - withh

        print(f"{ticker:<10} | {date_str:<12} | {gross:>12.2f} | {withh:>12.2f} | {net:>12.2f}")

    # Generate XML
    NS_EDP = "http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd"
    NS_MAIN = "http://edavki.durs.si/Documents/Schemas/Doh_Div_3.xsd"

    ET.register_namespace('edp', NS_EDP)
    ET.register_namespace('', NS_MAIN)

    root = ET.Element(f"{{{NS_MAIN}}}Envelope")

    # Header
    header = ET.SubElement(root, f"{{{NS_EDP}}}Header")
    taxpayer = ET.SubElement(header, f"{{{NS_EDP}}}taxpayer")
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}taxNumber").text = settings.TAX_NUMBER
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}taxpayerType").text = "FO"
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}name").text = settings.NAME
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}address1").text = settings.ADDRESS
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}city").text = settings.CITY
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}postNumber").text = settings.POST_NUMBER
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}postName").text = settings.POST_NAME

    ET.SubElement(root, f"{{{NS_EDP}}}AttachmentList")
    ET.SubElement(root, f"{{{NS_EDP}}}Signatures")

    # Body
    body = ET.SubElement(root, "body")

    # Doh_Div main element
    doh_div = ET.SubElement(body, f"{{{NS_MAIN}}}Doh_Div")
    ET.SubElement(doh_div, f"{{{NS_MAIN}}}Period").text = str(settings.TAX_YEAR)
    ET.SubElement(doh_div, f"{{{NS_MAIN}}}EmailAddress").text = settings.EMAIL
    ET.SubElement(doh_div, f"{{{NS_MAIN}}}PhoneNumber").text = settings.PHONE
    ET.SubElement(doh_div, f"{{{NS_MAIN}}}ResidentCountry").text = "SI"
    ET.SubElement(doh_div, f"{{{NS_MAIN}}}IsResident").text = "true"

    # Add dividend entries
    for _, row in df_dividends.iterrows():
        dividend = ET.SubElement(body, f"{{{NS_MAIN}}}Dividend")

        # Date
        ET.SubElement(dividend, f"{{{NS_MAIN}}}Date").text = row['Time'].strftime('%Y-%m-%d')

        # Payer information (company name from ticker/ISIN)
        company_name = f"{row['Name']} ({row['Ticker']})"
        ET.SubElement(dividend, f"{{{NS_MAIN}}}PayerName").text = company_name

        # Country from ISIN
        country = get_country_from_isin(row['ISIN'])
        ET.SubElement(dividend, f"{{{NS_MAIN}}}PayerCountry").text = country
        ET.SubElement(dividend, f"{{{NS_MAIN}}}SourceCountry").text = country

        # Type of dividend
        ET.SubElement(dividend, f"{{{NS_MAIN}}}Type").text = "Dividenda"

        # Gross dividend amount in EUR
        gross_eur = row['Gross_EUR']
        ET.SubElement(dividend, f"{{{NS_MAIN}}}Value").text = f"{gross_eur:.2f}"

        # Foreign tax withheld in EUR
        withholding_eur = row['Withholding_EUR']
        ET.SubElement(dividend, f"{{{NS_MAIN}}}ForeignTax").text = f"{withholding_eur:.2f}"

        # Relief statement (claiming tax treaty benefits)
        if country == 'US' and withholding_eur > 0:
            ET.SubElement(dividend, f"{{{NS_MAIN}}}ReliefStatement").text = "DA"

    # Pretty print XML
    xml_str = ET.tostring(root, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="\t").replace('xmlns:default', 'xmlns')

    # Save to file
    base_fn = f"Doh_Div_{settings.TAX_YEAR}"
    filename = f"{base_fn}.xml"
    out_path = os.path.join(settings.OUTPUT_FOLDER, filename)
    c = 1
    while os.path.exists(out_path):
        filename = f"{base_fn}_v{c:02d}.xml"
        out_path = os.path.join(settings.OUTPUT_FOLDER, filename)
        c += 1

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"\n✅ XML za dividende shranjen: {filename}")
    print(f"📋 Datoteka je pripravljena za uvoz v eDavke (Doh-Div obrazec)")


if __name__ == "__main__":
    print("Ta modul se izvaja kot del main.py")
    print("Poženi: python main.py")

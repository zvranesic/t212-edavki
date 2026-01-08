import pandas as pd
import os
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import deque
import ctypes

# Omogoči barve v Windows terminalu
kernel32 = ctypes.windll.kernel32
kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

# Uvoz nastavitev
try:
    import settings
except ImportError:
    print("Napaka: Datoteka settings.py ne obstaja!")
    exit()


def fetch_ecb_rates():
    print("Prenašam aktualne tečaje z ECB...")
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            with z.open('eurofxref-hist.csv') as f:
                rates_df = pd.read_csv(f)
        rates_df = rates_df[['Date', 'USD', 'GBP']]
        rates_df['Date'] = pd.to_datetime(rates_df['Date'])
        rates_df = rates_df.sort_values('Date').ffill()
        return rates_df
    except Exception as e:
        print(f"Napaka pri pridobivanju tečajev: {e}")
        return None


def format_high_precision(val):
    if val is None:
        return "0.0000"
    return f"{float(val):.8f}".rstrip('0').rstrip('.')


def create_edavki_xml():
    if not os.path.exists(settings.OUTPUT_FOLDER):
        os.makedirs(settings.OUTPUT_FOLDER)

    rates_df = fetch_ecb_rates()
    if rates_df is None:
        return

    csv_files = [f for f in os.listdir(
        settings.INPUT_FOLDER) if f.endswith('.csv')]
    if not csv_files:
        print("Napaka: Ni datotek v mapi /input!")
        return

    all_dfs = []
    for file in csv_files:
        all_dfs.append(pd.read_csv(os.path.join(settings.INPUT_FOLDER, file)))

    df = pd.concat(all_dfs, ignore_index=True)
    df['Time'] = pd.to_datetime(df['Time']).dt.floor('s')
    df = df.drop_duplicates(
        subset=['Time', 'Action', 'ISIN', 'No. of shares', 'Price / share'])
    df = df.sort_values('Time')

    df_trades = df[df['Action'].str.contains(
        'buy|sell', case=False, na=False)].copy()

    for isin, split_date, ratio in settings.STOCK_SPLITS:
        split_dt = pd.to_datetime(split_date)
        mask = (df_trades['ISIN'] == isin) & (df_trades['Time'] < split_dt)
        df_trades.loc[mask, 'No. of shares'] = df_trades.loc[mask,
                                                             'No. of shares'] * ratio
        df_trades.loc[mask, 'Price / share'] = df_trades.loc[mask,
                                                             'Price / share'] / ratio

    df_trades['Date_only'] = df_trades['Time'].dt.normalize()
    df_trades = pd.merge_asof(
        df_trades, rates_df, left_on='Date_only', right_on='Date', direction='backward')

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

    df_trades['Price_EUR'] = df_trades.apply(to_eur, axis=1)
    df_trades['Year_val'] = df_trades['Time'].dt.year

    # --- FIFO LOGIKA ---
    inventory = {}
    yearly_stats = {}  # {ISIN: {ticker, real_pl, furs_pl}}
    total_real_pl = 0.0
    total_furs_pl = 0.0

    for _, row in df_trades.iterrows():
        isin = row['ISIN']
        ticker = row['Ticker']
        qty = float(row['No. of shares'])
        price_eur = float(row['Price_EUR'])
        is_buy = "buy" in row['Action'].lower()

        if isin not in inventory:
            inventory[isin] = deque()
        if isin not in yearly_stats:
            yearly_stats[isin] = {'ticker': ticker, 'real': 0.0, 'furs': 0.0}

        if is_buy:
            inventory[isin].append({'qty': qty, 'price': price_eur})
        else:
            temp_qty = qty
            while temp_qty > 0 and inventory[isin]:
                oldest_buy = inventory[isin][0]
                sell_from_this_batch = min(temp_qty, oldest_buy['qty'])

                if row['Year_val'] == settings.TAX_YEAR:
                    # Realen profit (brez 1% provizij)
                    real_profit = (
                        price_eur - oldest_buy['price']) * sell_from_this_batch
                    # FURS profit (z 1% provizij)
                    furs_profit = (
                        price_eur * 0.99 - oldest_buy['price'] * 1.01) * sell_from_this_batch

                    yearly_stats[isin]['real'] += real_profit
                    yearly_stats[isin]['furs'] += furs_profit
                    total_real_pl += real_profit
                    total_furs_pl += furs_profit

                oldest_buy['qty'] -= sell_from_this_batch
                temp_qty -= sell_from_this_batch
                if oldest_buy['qty'] <= 1e-9:
                    inventory[isin].popleft()

    # --- LEP IZPIS V TERMINAL ---
    C_GREEN = "\033[92m"
    C_RED = "\033[91m"
    C_BOLD = "\033[1m"
    C_END = "\033[0m"

    print("\n" + "╔" + "═"*60 + "╗")
    print(f"║ {C_BOLD}DAVČNO POROČILO ZA LETO {settings.TAX_YEAR}{C_END:<36} ║")
    print("╠" + "═"*60 + "╣")

    real_col = C_GREEN if total_real_pl >= 0 else C_RED
    furs_col = C_GREEN if total_furs_pl >= 0 else C_RED

    print(
        f"║ REALIZIRAN DOBIČEK (REALNO):        {real_col}{total_real_pl:>15.2f} EUR{C_END} ║")
    print(
        f"║ REALIZIRAN DOBIČEK (FURS):          {furs_col}{total_furs_pl:>15.2f} EUR{C_END} ║")

    tax_amount = max(0, total_furs_pl * settings.TAX_RATE)
    print(
        f"║ PREDVIDEN DAVEK ({settings.TAX_RATE*100:.0f}% OD FURS):      {C_BOLD}{tax_amount:>15.2f} EUR{C_END} ║")
    print("╚" + "═"*60 + "╝")

    print(f"\n📑 PREGLED PO TRGOVANIH DELNICAH V LETU {settings.TAX_YEAR}:")
    print(f"{'TICKER':<10} | {'REALNI P/L':>15} | {'FURS P/L':>15}")
    print("-" * 46)

    for isin, data in yearly_stats.items():
        if abs(data['real']) > 0.001 or abs(data['furs']) > 0.001:
            r_c = C_GREEN if data['real'] >= 0 else C_RED
            f_c = C_GREEN if data['furs'] >= 0 else C_RED
            print(
                f"{str(data['ticker']):<10} | {r_c}{data['real']:>15.2f}{C_END} | {f_c}{data['furs']:>15.2f}{C_END}")

    print(f"\n📊 TRENUTNO STANJE NA RAČUNU (PORTFELJ):")
    print(f"{'TICKER':<10} | {'KOLIČINA':>15} | {'NABAVNA VREDNOST (EUR)':>22}")
    print("-" * 55)

    portfolio_total_value = 0
    for isin, batches in inventory.items():
        rem_qty = sum(b['qty'] for b in batches)
        if rem_qty > 0.00001:
            ticker = df_trades[df_trades['ISIN'] == isin]['Ticker'].iloc[0]
            book_value = sum(b['qty'] * b['price'] for b in batches)
            portfolio_total_value += book_value
            print(f"{str(ticker):<10} | {rem_qty:>15.5f} | {book_value:>22.2f}")

    print("-" * 55)
    print(f"{'SKUPAJ':<10} | {'':>15} | {C_BOLD}{portfolio_total_value:>22.2f} EUR{C_END}")

    # --- XML GENERACIJA ---
    NS_EDP = "http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd"
    NS_MAIN = "http://edavki.durs.si/Documents/Schemas/Doh_KDVP_9.xsd"
    ET.register_namespace('edp', NS_EDP)
    ET.register_namespace('', NS_MAIN)
    root = ET.Element(f"{{{NS_MAIN}}}Envelope")
    header = ET.SubElement(root, f"{{{NS_EDP}}}Header")
    taxpayer = ET.SubElement(header, f"{{{NS_EDP}}}taxpayer")
    ET.SubElement(
        taxpayer, f"{{{NS_EDP}}}taxNumber").text = settings.TAX_NUMBER
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}taxpayerType").text = "FO"
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}name").text = settings.NAME
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}address1").text = settings.ADDRESS
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}city").text = settings.CITY
    ET.SubElement(
        taxpayer, f"{{{NS_EDP}}}postNumber").text = settings.POST_NUMBER
    ET.SubElement(taxpayer, f"{{{NS_EDP}}}postName").text = settings.POST_NAME
    ET.SubElement(root, f"{{{NS_EDP}}}AttachmentList")
    ET.SubElement(root, f"{{{NS_EDP}}}Signatures")
    body = ET.SubElement(root, f"{{{NS_MAIN}}}body")
    ET.SubElement(body, f"{{{NS_EDP}}}bodyContent")
    doh_kdvp = ET.SubElement(body, f"{{{NS_MAIN}}}Doh_KDVP")

    isins_sold = df_trades[(df_trades['Action'].str.contains('sell', case=False)) & (
        df_trades['Year_val'] == settings.TAX_YEAR)]['ISIN'].unique()

    kdvp = ET.SubElement(doh_kdvp, f"{{{NS_MAIN}}}KDVP")
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}DocumentWorkflowID").text = "O"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}Year").text = str(settings.TAX_YEAR)
    ET.SubElement(
        kdvp, f"{{{NS_MAIN}}}PeriodStart").text = f"{settings.TAX_YEAR}-01-01"
    ET.SubElement(
        kdvp, f"{{{NS_MAIN}}}PeriodEnd").text = f"{settings.TAX_YEAR}-12-31"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}IsResident").text = "true"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}TelephoneNumber").text = settings.PHONE
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}SecurityCount").text = str(
        len(isins_sold))
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}SecurityShortCount").text = "0"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}SecurityWithContractCount").text = "0"
    ET.SubElement(
        kdvp, f"{{{NS_MAIN}}}SecurityWithContractShortCount").text = "0"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}ShareCount").text = "0"
    ET.SubElement(
        kdvp, f"{{{NS_MAIN}}}SecurityCapitalReductionCount").text = "0"
    ET.SubElement(kdvp, f"{{{NS_MAIN}}}Email").text = settings.EMAIL

    for isin in isins_sold:
        ticker = df_trades[df_trades['ISIN'] == isin]['Ticker'].iloc[0]
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

        # Pametna simulacija za XML (FIFO)
        temp_inv = deque()
        xml_rows = []
        group = df_trades[df_trades['ISIN'] == isin].copy()

        for _, row in group.iterrows():
            q = float(row['No. of shares'])
            buy = "buy" in row['Action'].lower()
            if buy:
                temp_inv.append(
                    {'qty': q, 'price': row['Price_EUR'], 'time': row['Time'], 'year': row['Year_val']})
                # Če je nakup v tekočem letu, gre direktno v XML
                if row['Year_val'] == settings.TAX_YEAR:
                    xml_rows.append(
                        {'type': 'B', 'date': row['Time'], 'qty': q, 'price': row['Price_EUR']})
            else:
                t_qty = q
                while t_qty > 0 and temp_inv:
                    o_buy = temp_inv[0]
                    take = min(t_qty, o_buy['qty'])

                    # Če je star nakup prodan v tekočem letu, ga moramo vključiti v XML
                    if o_buy['year'] < settings.TAX_YEAR and row['Year_val'] == settings.TAX_YEAR:
                        if not any(x['type'] == 'B' and x['date'] == o_buy['time'] for x in xml_rows):
                            xml_rows.append(
                                {'type': 'B', 'date': o_buy['time'], 'qty': o_buy['qty'], 'price': o_buy['price']})

                    o_buy['qty'] -= take
                    t_qty -= take
                    if o_buy['qty'] <= 1e-9:
                        temp_inv.popleft()

                # Prodaja v tekočem letu gre vedno v XML
                if row['Year_val'] == settings.TAX_YEAR:
                    xml_rows.append(
                        {'type': 'S', 'date': row['Time'], 'qty': q, 'price': row['Price_EUR']})

        # Zapis vrstic v XML (urejeno po datumu)
        xml_rows.sort(key=lambda x: x['date'])
        run_qty = 0.0
        for idx, xr in enumerate(xml_rows):
            xml_row = ET.SubElement(securities, f"{{{NS_MAIN}}}Row")
            ET.SubElement(xml_row, f"{{{NS_MAIN}}}ID").text = str(idx)
            if xr['type'] == 'B':
                run_qty += xr['qty']
                p = ET.SubElement(xml_row, f"{{{NS_MAIN}}}Purchase")
                ET.SubElement(p, f"{{{NS_MAIN}}}F1").text = xr['date'].strftime(
                    '%Y-%m-%d')
                ET.SubElement(p, f"{{{NS_MAIN}}}F2").text = "B"
                ET.SubElement(
                    p, f"{{{NS_MAIN}}}F3").text = format_high_precision(xr['qty'])
                ET.SubElement(p, f"{{{NS_MAIN}}}F4").text = format_high_precision(
                    xr['price'])
                ET.SubElement(p, f"{{{NS_MAIN}}}F5").text = "0.0000"
            else:
                run_qty -= xr['qty']
                s = ET.SubElement(xml_row, f"{{{NS_MAIN}}}Sale")
                ET.SubElement(s, f"{{{NS_MAIN}}}F6").text = xr['date'].strftime(
                    '%Y-%m-%d')
                ET.SubElement(
                    s, f"{{{NS_MAIN}}}F7").text = format_high_precision(xr['qty'])
                ET.SubElement(s, f"{{{NS_MAIN}}}F9").text = format_high_precision(
                    xr['price'])

            if abs(run_qty) < 1e-9:
                run_qty = 0.0
            ET.SubElement(
                xml_row, f"{{{NS_MAIN}}}F8").text = format_high_precision(run_qty)

    xml_str = ET.tostring(root, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(
        indent="\t").replace('xmlns:default', 'xmlns')

    base_fn = f"Doh_KDVP_{settings.TAX_YEAR}"
    filename = f"{base_fn}.xml"
    out_path = os.path.join(settings.OUTPUT_FOLDER, filename)
    c = 1
    while os.path.exists(out_path):
        filename = f"{base_fn}_v{c:02d}.xml"
        out_path = os.path.join(settings.OUTPUT_FOLDER, filename)
        c += 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
    print(f"\n✅ XML shranjen: {filename}")
    print(f"🚀 Pripravljeno za oddajo na eDavke!")


if __name__ == "__main__":
    create_edavki_xml()

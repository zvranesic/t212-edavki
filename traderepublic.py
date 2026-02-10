"""
Trade Republic PDF Statement Parser
Converts Trade Republic account statements (PDF) to Trading 212 CSV format
for compatibility with existing tax reporting tools.
"""

import pypdf
import re
import pandas as pd
from datetime import datetime
from decimal import Decimal


def parse_traderepublic_pdf(pdf_path):
    """
    Parse Trade Republic PDF statement and return DataFrame in Trading 212 CSV format.
    
    Returns:
        pd.DataFrame with columns: Action, Time, ISIN, Ticker, Name, 
                                   No. of shares, Price / share, Currency code,
                                   Exchange rate, Total (EUR), Withholding tax
    """
    
    with open(pdf_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        
        # Extract all text from PDF
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
    
    # Parse transactions
    transactions = []
    dividends = []
    
    lines = full_text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]  # Don't strip yet, we need to detect trailing space
        line_stripped = line.strip()
        
        # Look for date lines that end with space: "DD Mon "
        if line.endswith(' ') or line.endswith('\t'):
            date_match = re.match(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*$', line_stripped)
            if date_match and i + 1 < len(lines):
                day = date_match.group(1)
                month = date_match.group(2)
                
                # Next line has: year, type, and description
                next_line = lines[i + 1].strip()
                
                # Try to match: "2025 Trade Buy trade ..." or "2025 Trade Sell trade..."
                trade_match = re.match(r'(\d{4})\s+Trade\s+(Buy trade|Sell trade)\s+(.+)', next_line)
                if trade_match:
                    year = trade_match.group(1)
                    action = trade_match.group(2)
                    description = trade_match.group(3)
                    
                    # Check if description continues on next line (for long names)
                    if i + 2 < len(lines):
                        line_after = lines[i + 2].strip()
                        # If next line doesn't start with a date or is a continuation
                        if not re.match(r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', line_after):
                            # It's a continuation
                            description += " " + line_after
                    
                    transaction = parse_trade_transaction_new(
                        day, month, year, action, description
                    )
                    if transaction:
                        transactions.append(transaction)
                
                # Check for dividend
                dividend_match = re.match(r'(\d{4})\s+Earnings\s+(.+)', next_line)
                if dividend_match:
                    year = dividend_match.group(1)
                    description = dividend_match.group(2)
                    
                    if 'Cash Dividend' in description:
                        dividend = parse_dividend_transaction_new(
                            day, month, year, description, lines, i + 1
                        )
                        if dividend:
                            dividends.append(dividend)
        
        i += 1
    
    # Convert to DataFrame
    if not transactions and not dividends:
        return pd.DataFrame()
    
    # Combine transactions and dividends
    all_data = transactions + dividends
    df = pd.DataFrame(all_data)
    
    # Ensure proper column order matching Trading 212 format
    columns = [
        'Action', 'Time', 'ISIN', 'Ticker', 'Name', 
        'No. of shares', 'Price / share', 'Currency code',
        'Exchange rate', 'Total (EUR)', 'Withholding tax'
    ]
    
    for col in columns:
        if col not in df.columns:
            df[col] = None
    
    df = df[columns]
    
    return df


def parse_trade_transaction_new(day, month, year, action, description):
    """Parse a buy/sell trade transaction from combined description."""
    
    # Determine action type
    if action == 'Buy trade':
        action_type = 'Market buy'
    elif action == 'Sell trade':
        action_type = 'Market sell'
    else:
        return None
    
    # Extract ISIN (12 characters)
    isin_match = re.search(r'([A-Z]{2}[A-Z0-9]{10})', description)
    if not isin_match:
        return None
    isin = isin_match.group(1)
    
    # Extract name (after ISIN, before "quantity:")
    name_match = re.search(r'[A-Z]{2}[A-Z0-9]{10}\s+(.+?),?\s+quantity:', description)
    name = name_match.group(1).strip() if name_match else "Unknown"
    
    # Extract quantity
    quantity_match = re.search(r'quantity:\s*([\d.]+)', description)
    if not quantity_match:
        return None
    quantity = quantity_match.group(1)
    
    # Extract amount (€XXX.XX format)
    amount_match = re.search(r'€([\d,]+\.\d{2})', description)
    if not amount_match:
        return None
    
    amount_str = amount_match.group(1).replace(',', '')
    total_eur = Decimal(amount_str)
    
    # Calculate price per share
    qty_decimal = Decimal(quantity)
    price_per_share = total_eur / qty_decimal if qty_decimal != 0 else Decimal(0)
    
    # Parse date
    month_num = datetime.strptime(month, '%b').month
    date_str = f"{year}-{month_num:02d}-{day.zfill(2)}"
    time_str = f"{date_str} 12:00:00"
    
    # Extract ticker from name
    ticker = extract_ticker(name, isin)
    
    return {
        'Action': action_type,
        'Time': time_str,
        'ISIN': isin,
        'Ticker': ticker,
        'Name': name,
        'No. of shares': quantity,
        'Price / share': str(price_per_share),
        'Currency code': 'EUR',
        'Exchange rate': None,
        'Total (EUR)': str(total_eur),
        'Withholding tax': None
    }


def parse_dividend_transaction_new(day, month, year, description, lines, line_idx):
    """Parse a dividend transaction from description."""
    
    # Extract ISIN from description
    isin_match = re.search(r'ISIN\s+([A-Z]{2}[A-Z0-9]{10})', description)
    if not isin_match:
        return None
    isin = isin_match.group(1)
    
    # Extract amount - might be on same line or next line
    amount_match = re.search(r'€([\d,]+\.\d{2})', description)
    if not amount_match and line_idx + 1 < len(lines):
        next_line = lines[line_idx + 1].strip()
        amount_match = re.search(r'€([\d,]+\.\d{2})', next_line)
    
    if not amount_match:
        return None
    
    amount = amount_match.group(1).replace(',', '')
    
    # Parse date
    month_num = datetime.strptime(month, '%b').month
    date_str = f"{year}-{month_num:02d}-{day.zfill(2)}"
    time_str = f"{date_str} 12:00:00"
    
    return {
        'Action': 'Dividend (Dividend)',
        'Time': time_str,
        'ISIN': isin,
        'Ticker': isin,  # Use full ISIN for dividends
        'Name': f'Dividend for {isin}',
        'No. of shares': None,
        'Price / share': None,
        'Currency code': 'EUR',
        'Exchange rate': None,
        'Total (EUR)': amount,
        'Withholding tax': None
    }


def parse_trade_transaction(day, month, year, trade_line, lines, line_idx):
    """Parse a buy/sell trade transaction."""
    
    # Determine action
    if 'Buy trade' in trade_line:
        action = 'Market buy'
    elif 'Sell trade' in trade_line:
        action = 'Market sell'
    else:
        return None
    
    # Extract ISIN (12 characters at start of ISIN code)
    isin_match = re.search(r'([A-Z]{2}[A-Z0-9]{10})', trade_line)
    if not isin_match:
        return None
    isin = isin_match.group(1)
    
    # Extract name (after ISIN, before "quantity:")
    name_match = re.search(r'[A-Z]{2}[A-Z0-9]{10}\s+(.+?),?\s+quantity:', trade_line)
    name = name_match.group(1).strip() if name_match else "Unknown"
    
    # Extract quantity - look in current line and next lines
    quantity_match = re.search(r'quantity:\s*([\d.]+)', trade_line)
    if not quantity_match and line_idx + 1 < len(lines):
        # Quantity might be on next line
        next_line = lines[line_idx + 1].strip()
        quantity_match = re.search(r'quantity:\s*([\d.]+)', next_line)
        if quantity_match:
            trade_line += " " + next_line
    
    if not quantity_match:
        return None
    quantity = quantity_match.group(1)
    
    # Extract amount (€XXX.XX format)
    amount_match = re.search(r'€([\d,]+\.\d{2})', trade_line)
    if not amount_match and line_idx + 1 < len(lines):
        next_line = lines[line_idx + 1].strip()
        amount_match = re.search(r'€([\d,]+\.\d{2})', next_line)
    
    if not amount_match:
        return None
    
    amount_str = amount_match.group(1).replace(',', '')
    total_eur = Decimal(amount_str)
    
    # Calculate price per share
    qty_decimal = Decimal(quantity)
    price_per_share = total_eur / qty_decimal if qty_decimal != 0 else Decimal(0)
    
    # Parse date
    month_num = datetime.strptime(month, '%b').month
    # Extract year from year line
    year_match = re.search(r'(\d{4})', year)
    year_val = year_match.group(1) if year_match else '2025'
    
    date_str = f"{year_val}-{month_num:02d}-{day.zfill(2)}"
    time_str = f"{date_str} 12:00:00"  # Trade Republic doesn't provide exact time
    
    # Extract ticker from name (best effort)
    ticker = extract_ticker(name, isin)
    
    return {
        'Action': action,
        'Time': time_str,
        'ISIN': isin,
        'Ticker': ticker,
        'Name': name,
        'No. of shares': quantity,
        'Price / share': str(price_per_share),
        'Currency code': 'EUR',
        'Exchange rate': None,
        'Total (EUR)': str(total_eur),
        'Withholding tax': None
    }


def parse_dividend_transaction(day, month, year, dividend_line, lines, line_idx):
    """Parse a dividend transaction."""
    
    # Extract ISIN
    isin_match = re.search(r'ISIN\s+([A-Z]{2}[A-Z0-9]{10})', dividend_line)
    if not isin_match:
        return None
    isin = isin_match.group(1)
    
    # Extract amount from next line
    amount = None
    if line_idx + 1 < len(lines):
        next_line = lines[line_idx + 1].strip()
        amount_match = re.search(r'€([\d,]+\.\d{2})', next_line)
        if amount_match:
            amount = amount_match.group(1).replace(',', '')
    
    if not amount:
        return None
    
    # Parse date
    month_num = datetime.strptime(month, '%b').month
    year_match = re.search(r'(\d{4})', year)
    year_val = year_match.group(1) if year_match else '2025'
    
    date_str = f"{year_val}-{month_num:02d}-{day.zfill(2)}"
    time_str = f"{date_str} 12:00:00"
    
    return {
        'Action': 'Dividend (Dividend)',
        'Time': time_str,
        'ISIN': isin,
        'Ticker': isin[:6],  # Placeholder
        'Name': f'Dividend for {isin}',
        'No. of shares': None,
        'Price / share': None,
        'Currency code': 'EUR',
        'Exchange rate': None,
        'Total (EUR)': amount,
        'Withholding tax': None  # Trade Republic doesn't show withholding in statement
    }


def extract_ticker(name, isin):
    """Extract ticker symbol from security name or use ISIN if unknown."""
    
    # Only map well-known US stocks where we're confident
    if 'PALANTIR' in name.upper():
        return 'PLTR'
    elif 'ALPHABET' in name.upper() or 'GOOGLE' in name.upper():
        return 'GOOG'
    elif 'TESLA' in name.upper():
        return 'TSLA'
    elif 'BITCOIN' in name.upper():
        return 'BTC'
    
    # For everything else (ETFs, international stocks, unknown), use ISIN
    # The ISIN is the authoritative identifier anyway
    return isin


def convert_traderepublic_to_csv(pdf_path, output_csv_path):
    """
    Convert Trade Republic PDF to CSV file in Trading 212 format.
    
    Args:
        pdf_path: Path to Trade Republic PDF statement
        output_csv_path: Path where CSV should be saved
    """
    df = parse_traderepublic_pdf(pdf_path)
    
    if df.empty:
        print("No transactions found in PDF")
        return
    
    df.to_csv(output_csv_path, index=False)
    print(f"✅ Converted {len(df)} transactions to {output_csv_path}")


if __name__ == "__main__":
    # Test the parser
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "input/traderepublic_statement.pdf"
    
    df = parse_traderepublic_pdf(pdf_path)
    
    if not df.empty:
        print(f"\n✅ Parsed {len(df)} transactions from Trade Republic PDF\n")
        print(df.to_string())
        print(f"\nSample transactions:")
        print(df.head(10))
    else:
        print("❌ No transactions found")

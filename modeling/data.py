from datetime import datetime 
from urllib.request import urlopen, Request
import json
import pandas as pd
import os
import time
import yfinance as yf

# --- 1. THE CONVERTER ---

def convert_json_to_csv(ticker, folder):
    """Reads data.json and creates CSVs ONLY for financial statements"""
    json_path = os.path.join(folder, 'data.json')
    
    try:
        with open(json_path, 'r') as f:
            master_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: data.json not found in {folder}!")
        return
    
    statements_to_convert = [
        "income_statement", 
        "balance_statement", 
        "cashflow_statement", 
        "enterprise_value_statement"
    ]

    print(f"--- 📂 Converting Financial Statements to CSVs in {folder} ---")

    for key in statements_to_convert:
        data = master_data.get(key)
        if data and isinstance(data, list) and len(data) > 0:
            try:
                df = pd.DataFrame(data)
                if 'date' in df.columns:
                    df.set_index('date', inplace=True)
                
                df_transposed = df.transpose()
                csv_path = os.path.join(folder, f"{ticker}_{key}.csv")
                
                with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                    df_transposed.to_csv(f, index=True, sep=';')
                print(f"   ✅ Saved: {ticker}_{key}.csv")
            except Exception as e:
                print(f"   ⚠️ Could not convert {key}: {e}")
        else:
            print(f"   ⏭️ Skipping {key}: No data found.")

# --- 2. THE FETCHER ---

def fetch_financials(ticker, apikey, folder):
    """Fetches data from API and saves it to a ticker-specific folder"""
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
        print(f"📂 Created new directory: {folder}")

    base_url = "https://financialmodelingprep.com/stable"
    v3_url = "https://financialmodelingprep.com/api/v3"
    endpoints = {
        "income_statement": f"{base_url}/income-statement?symbol={ticker}&period=annual&apikey={apikey}",
        "balance_statement": f"{base_url}/balance-sheet-statement?symbol={ticker}&period=annual&apikey={apikey}",
        "cashflow_statement": f"{base_url}/cash-flow-statement?symbol={ticker}&period=annual&apikey={apikey}",
        "enterprise_value_statement": f"{base_url}/enterprise-values?symbol={ticker}&period=annual&apikey={apikey}",
        "quote": f"{v3_url}/quote/{ticker}?apikey={apikey}",
        "profile": f"{v3_url}/profile/{ticker}?apikey={apikey}"
    }
        
    master_data = {"metadata": {"ticker": ticker, "retrieved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    
    for key, url in endpoints.items():
        print(f"Requesting {key}...")
        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                master_data[key] = data if data else []
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Error on {key}: {e}")
            master_data[key] = []

    save_path = os.path.join(folder, "data.json")
    with open(save_path, "w") as f:
        json.dump(master_data, f, indent=4)
    
    return master_data

import yfinance as yf

def get_market_data(ticker_symbol):
    stock = yf.Ticker(ticker_symbol)
    
    info = stock.info
    full_name = info.get('longName', ticker_symbol)
    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
    
    history_df = stock.history(period="5y")
    history_list = history_df['Close'].tolist()
    
    return {
        "full_name": full_name,
        "current_price": current_price,
        "history": history_list,
        "history_df": history_df
    }

# --- 3. THE TEMPLATER ---

def create_assumption_template(ticker, output_folder, company_name="Unknown"):
    """Creates a wide-format CSV for 10-year dynamic DCF assumptions"""
    assumption_path = os.path.join(output_folder, f"{ticker}_assumptions.csv")
    
    if os.path.exists(assumption_path):
        return

    # 1. Define the rows (The Metrics)
    metrics = [
        "revenue_growth", 
        "ebit_margin_delta", 
        "capex_delta", 
        "wacc", 
        "perpetual_growth", 
        "forecast_years"
    ]
    
    # 2. Define the starting/fallback values
    defaults = [0.05, 0.0, 0.0, 0.085, 0.02, 5]
    
    descriptions = [
        "Annual revenue growth (0.05 = 5%)",
        "Change to base EBIT margin (0.02 = +2%)",
        "CapEx adjustment relative to revenue growth",
        "Discount rate (Constant)",
        "Terminal growth rate",
        "Total forecast horizon (Years)"
    ]

    # 3. Build the Dictionary with 10 Year slots
    data = {
        "Assumption": metrics,
        "Default": defaults
    }
    
    # Add empty slots for Year 1 through Year 10
    for i in range(1, 11):
        data[f"Year {i}"] = [""] * len(metrics)
    
    data["Description"] = descriptions

    df = pd.DataFrame(data)
    
    with open(assumption_path, 'w', newline='', encoding='utf-8') as f:
        f.write(f"Company Name;{company_name}\n")
        f.write(f"Ticker;{ticker}\n")
        f.write("\n")
        df.to_csv(f, index=False, sep=';')
        
# --- 4. LOCAL TESTING BLOCK ---

if __name__ == "__main__":
    ticker = 'KO'
    apikey = 'YOUR_KEY' 
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to the root, then into output/
    project_root = os.path.dirname(script_dir) 
    folder = os.path.join(project_root, "output", ticker)
    
    fetch_financials(ticker, apikey, folder)
    convert_json_to_csv(ticker, folder)
    create_assumption_template(ticker, folder)
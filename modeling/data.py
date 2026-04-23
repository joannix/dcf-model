"""
Utilizing financialmodelingprep.com for their free-endpoint API
to gather company financials.
"""
from urllib.request import urlopen, Request
import json
import pandas as pd
import os
import time
from json_to_csv import convert_json_to_csv 

# --- FUNCTION DEFINITIONS (The Machines) ---

def fetch_financials(ticker, apikey):
    base_url = "https://financialmodelingprep.com/stable"
    endpoints = {
        "income_statement": f"{base_url}/income-statement?symbol={ticker}&period=annual&apikey={apikey}",
        "balance_statement": f"{base_url}/balance-sheet-statement?symbol={ticker}&period=annual&apikey={apikey}",
        "cashflow_statement": f"{base_url}/cash-flow-statement?symbol={ticker}&period=annual&apikey={apikey}",
        "enterprise_value_statement": f"{base_url}/enterprise-values?symbol={ticker}&period=annual&apikey={apikey}"
    }
        
    master_data = {}
    for key, url in endpoints.items():
        print(f"Requesting {key}...")
        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            if isinstance(data, list) and len(data) > 0:
                print(f"   ✅ SUCCESS: Received {len(data)} years of data.")
                master_data[key] = data
            elif isinstance(data, dict) and "Error Message" in data:
                print(f"   ❌ API Rejected: {data['Error Message']}")
            else:
                print(f"   ⚠️ Warning: No data found.")
            
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Connection Error: {e}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'data.json')
    with open(file_path, 'w') as f:
        json.dump(master_data, f, indent=4)
    print(f"\n--- DONE: Master data updated in {file_path} ---")

def create_assumption_template(ticker, output_folder):
    assumption_path = os.path.join(output_folder, f"{ticker}_assumptions.csv")
    
    # SAFETY LOCK: Do not overwrite if you already spent time filling it in!
    if os.path.exists(assumption_path):
        print(f"ℹ️  Assumptions file already exists for {ticker}. Skipping template creation.")
        return

    # Standard Analyst Defaults
    data = {
        "Assumption": [
            "ebit_growth", "capex_growth", "wacc", 
            "perpetual_growth", "forecast_years", "current_market_price"
        ],
        "Value": [0.15, 0.05, 0.085, 0.02, 5, 185.00],
        "Description": [
            "Annual EBIT growth (decimal)", "Annual CapEx growth (decimal)", 
            "Discount Rate / WACC (decimal)", "Terminal Growth Rate (decimal)", 
            "Years to forecast (integer)", "Today's trading price"
        ]
    }
    
    df = pd.DataFrame(data)
    
    # Save with the Polish Excel fix (sep=,)
    with open(assumption_path, 'w', encoding='utf-8', newline='') as f:
        f.write("sep=,\n")
        df.to_csv(f, index=False)
    
    print(f"📝 Created fresh assumption template at: {assumption_path}")

# --- EXECUTION BLOCK (The Power Switch) ---

if __name__ == "__main__":
    ticker = 'AMZN'
    # Use your real API Key here
    apikey = 'OCXBJKPQcBYW4GwmYXGL34hfAv2HXb7T' 
    
    # 1. Download data to data.json
    fetch_financials(ticker, apikey)
    
    # 2. Convert data.json into separate CSVs in the ticker folder
    print(f"\nStarting conversion for {ticker}...")
    convert_json_to_csv(ticker)

    # 3. Setup folder path for the assumptions sheet
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, f"{ticker}_financials")

    # 4. Trigger the creation of the Assumptions Control Panel
    create_assumption_template(ticker, output_folder)
    
    print(f"\n--- ALL TASKS COMPLETE FOR {ticker} ---")
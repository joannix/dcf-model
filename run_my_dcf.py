import os
import json
import argparse
import pandas as pd
from dotenv import load_dotenv

from modeling.data import (fetch_financials, convert_json_to_csv, create_assumption_template, get_market_data)
from modeling.dcf import (enterprise_value, load_user_assumptions, run_sensitivity_analysis)

load_dotenv()  
ENV_API_KEY = os.getenv("FMP_API_KEY")

# --- HELPER: LOADS DATA ---
def load_local_data(ticker, folder):
    path = os.path.join(folder, "data.json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    print(f"❌ Error: Data file not found at {path}")
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--t', help='Stock Ticker', default='AAPL')
    parser.add_argument('--apikey', help="FMP API Key")
    parser.add_argument('--mode', choices=['setup', 'run'], default='setup', 
                        help='setup: downloads data | run: calculates valuation')
    args = parser.parse_args()

    active_api_key = args.apikey or ENV_API_KEY

    ticker = args.t.upper()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, "output", ticker)
    os.makedirs(output_folder, exist_ok=True)
    
    # --- STAGE 1: SETUP ---
    if args.mode == 'setup':
        
        if not active_api_key:
            print("❌ ERROR: No API Key found! Provide --apikey or set FMP_API_KEY in .env")
            return 
        
        print(f"--- 🛠️ STAGE 1: SETUP MODE ({ticker}) ---")
        
        master_data = fetch_financials(ticker, active_api_key, output_folder)
        yf_data = get_market_data(ticker)
        full_name = yf_data.get('full_name', ticker)
        profile_data = master_data.get('profile', [])
        if (not full_name or full_name == ticker) and profile_data:
            if isinstance(profile_data, list) and len(profile_data) > 0:
                full_name = profile_data[0].get('companyName', ticker)

        print(f"✅ Setup initialized for: {full_name}")
        
        convert_json_to_csv(ticker, output_folder) 
        create_assumption_template(ticker, output_folder, company_name=full_name)
        
        print(f"\n✅ Setup Complete! Now go to {output_folder}")
        print(f"👉 Edit '{ticker}_assumptions.csv' and save your changes.")
        print(f"🚀 When ready, run: python run_my_dcf.py --t {ticker} --mode run")

    # --- STAGE 2: RUN ---
    elif args.mode == 'run':
        print(f"--- 🧮 STAGE 2: VALUATION MODE ({ticker}) ---")
        
        # 1. LOAD DATA & ASSUMPTIONS
        master_data = load_local_data(ticker, output_folder)
        assumptions = load_user_assumptions(ticker, output_folder)
        yf_data = get_market_data(ticker)
        full_name = yf_data.get('full_name', ticker)
        print(f"✅ Valuation for: {full_name}")
            
        if not master_data or not assumptions:
            print("❌ Error: Missing local data or assumptions. Run --mode setup first.")
            return

        # 2. RUN CORE DCF MATH       
        results = enterprise_value(
            master_data['income_statement'],
            master_data['cashflow_statement'],
            master_data['balance_statement'],
            period=int(assumptions['forecast_years']),
            discount_rate=assumptions['wacc'],
            earnings_growth_rate=assumptions['revenue_growth'],
            capex_growth_rate=assumptions['capex_delta'],
            perpetual_growth_rate=assumptions['perpetual_growth'],
            assumptions=assumptions                             #
        )

        # 3. EQUITY BRIDGE
        bal_stmt = master_data['balance_statement'][0]
        ev_stmt = master_data['enterprise_value_statement'][0]
            
        # Extract the key values
        debt = float(bal_stmt.get('totalDebt', 0))
        cash = float(bal_stmt.get('cashAndCashEquivalents', 0))
        shares_outstanding = float(ev_stmt.get('numberOfShares', 0))
        
        equity_val = results['ev'] - debt + cash

        # SAFETY CHECK: Prevent dividing by zero
        if shares_outstanding > 0:
            intrinsic_price = equity_val / shares_outstanding
        else:
            print("⚠️ Warning: Could not find shares outstanding. Price set to 0.")
            intrinsic_price = 0

        # 4. GET MARKET PRICE AND DATE
        
        market_price = yf_data['current_price']
        company_name = yf_data['full_name']
        ev_data = master_data.get('enterprise_value_statement', [])
        price_source = "Yahoo Finance (Live)"

        # Fallback to last known price from EV statement
        if market_price == 0.0 and isinstance(ev_data, list) and len(ev_data) > 0:
            market_price = float(ev_data[0].get('stockPrice', 0))
            price_source = "FMP Filing Data (Last Fiscal Year)"
        elif market_price == 0.0:
            price_source = "Unknown (Data Unavailable)"

        # 5. DISPLAY MAIN REPORT
        metadata = master_data.get('metadata', {})
        price_date = metadata.get('retrieved_at', 'Unknown')
        print("\n" + "="*45)
        print(f"  🏢 DCF VALUATION REPORT: {full_name}")
        print(f"  📅 Data Captured: {price_date}")
        print(f"  🔍 Price Source:  {price_source}") # Tells you where the price came from
        print("="*45)

        # "Equity Bridge" section
        print(f"  Enterprise Value:     ${results['ev']/1e9:.2f}B")
        print(f"  (+) Cash:             ${cash/1e9:.2f}B")
        print(f"  (-) Total Debt:       ${debt/1e9:.2f}B")
        print(f"  (=) Equity Value:     ${equity_val/1e9:.2f}B")
        print(f"  (/) Shares Out:       {shares_outstanding/1e6:.2f}M")
        print("-" * 45)

        print(f"  ✨ INTRINSIC PRICE:    ${intrinsic_price:.2f}")
        print(f"  📉 MARKET PRICE:       ${market_price:.2f}")
        
        upside = 0.0
        if market_price > 0:
            upside = (intrinsic_price / market_price) - 1
            print(f"  🚀 UPSIDE/(DOWNSIDE):  {upside:.2f}%")
        print("="*45)
       
        # 6. SENSITIVITY ANALYSIS
        print("\n📊 SENSITIVITY ANALYSIS (Price per Share)")
            
        sensitivity_df = run_sensitivity_analysis(
            master_data['income_statement'],
            master_data['cashflow_statement'],
            master_data['balance_statement'],
            assumptions,
            debt, cash, shares_outstanding
        )
        print(sensitivity_df.to_string(index=False))
        print("="*45)

        # 7. SAVE TO DISK
        save_path = os.path.join(output_folder, f"valuation_output_{ticker}.csv")
        full_name = assumptions.get('company_full_name', ticker)
        with open(save_path, 'w', newline='', encoding='utf-8') as f:
            f.write(f"Company Name;{full_name}\n") 
            f.write(f"Ticker;{ticker}\n")
            f.write(f"Intrinsic Price;{intrinsic_price:.2f}\n")
            f.write(f"Market Price;{market_price:.2f}\n")
            f.write("\n") 
            
            f.write("--- FORECAST DATA ---\n")
            results['projections'].to_csv(f, index=False, sep=';')
            f.write("\n")

            f.write("--- VALUATION RESULTS ---\n")
            f.write(f"Intrinsic Price;{intrinsic_price:.2f}\n")
            f.write(f"Market Price;{market_price:.2f}\n")
            f.write(f"Upside/Downside;{upside:.2%}\n")
            f.write("\n")
            upside_val = ((intrinsic_price / market_price) - 1) * 100 if market_price > 0 else 0
            f.write("--- EQUITY BRIDGE COMPONENTS ---\n")
            f.write(f"Enterprise Value (EV);{results['ev']:.2f}\n")
            f.write(f"Add: Cash;{cash:.2f}\n")
            f.write(f"Less: Total Debt;{debt:.2f}\n")
            f.write(f"Equity Value;{equity_val:.2f}\n")
            f.write(f"Shares Outstanding;{shares_outstanding:.2f}\n")
            f.write("\n")    
                        
            f.write("--- SENSITIVITY ANALYSIS ---\n")
            
            sensitivity_df.to_csv(f, index=False, sep=';')
            
        print(f"✅ Report saved to: {save_path}")
       
        # 8. DATA FOR CHARTS
        chart_data = {
            "ticker": ticker,
            "company_name": yf_data['full_name'],
            "intrinsic_price": intrinsic_price,
            "market_price": yf_data['current_price'],
            "upside": upside,
            "ev": results['ev'],
            "ebit_history": results['ebit_history'],
            "ebit_hist_years": results['ebit_hist_years'],
            "ebit_forecast": results['ebit_forecast'].tolist() if hasattr(results['ebit_forecast'], 'tolist') else results['ebit_forecast'],
            "ebit_forecast_years": results['ebit_forecast_years'],
            "forecast_years": results['ebit_forecast_years'],
            "forecast_fcf": results.get('fcf_projections', [0]*5).tolist() if hasattr(results.get('fcf_projections'), 'tolist') else results.get('fcf_projections'),         
            "ebit_forecast_years": results['ebit_forecast_years'],
            "forecast_fcf": results.get('fcf_projections', [0, 0, 0, 0, 0]),
            "pv_forecast_sum": results.get('pv_sum', 0),
            "pv_terminal_value": results.get('pv_tv', 0),
            "cash": cash,
            "debt": debt,
            "equity_value": equity_val,
            "price_history": yf_data['history']
        }
        
        with open(f"output/{ticker}/chart_data.json", 'w') as f:
            json.dump(chart_data, f)
            print(f"✅ Chart data prepared at: {os.path.join(output_folder, 'chart_data.json')}")

if __name__ == "__main__":
    main()
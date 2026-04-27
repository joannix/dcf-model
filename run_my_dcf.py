import os
import json
import argparse
import pandas as pd
from modeling.data import fetch_financials, convert_json_to_csv, create_assumption_template
from modeling.dcf import enterprise_value, load_user_assumptions

# --- HELPER: LOADS DATA FROM STAGE 1 ---
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
    parser.add_argument('--apikey', help='API Key', default=None)
    parser.add_argument('--mode', choices=['setup', 'run'], default='setup', 
                        help='setup: downloads data | run: calculates valuation')
    args = parser.parse_args()

    ticker = args.t.upper()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # NEW STRUCTURE: dcf-model/output/KO/
    output_folder = os.path.join(script_dir, "output", ticker)

    # Ensure the output directory exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)
    
    # --- STAGE 1: SETUP ---
    if args.mode == 'setup':
        if not args.apikey:
            print("❌ ERROR: You must provide an --apikey to run 'setup' mode!")
            return 
        
        print(f"--- 🛠️ STAGE 1: SETUP MODE ({ticker}) ---")
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        master_data = fetch_financials(ticker, args.apikey, output_folder)
        
        # Ensure the data is saved in the ticker-specific folder
        convert_json_to_csv(ticker, output_folder) 
        create_assumption_template(ticker, output_folder)
        
        print(f"\n✅ Setup Complete! Now go to {output_folder}")
        print(f"👉 Edit '{ticker}_assumptions.csv' and save your changes.")
        print(f"🚀 When ready, run: python run_my_dcf.py --t {ticker} --mode run")

    # --- STAGE 2: RUN ---
    elif args.mode == 'run':
        print(f"--- 🧮 STAGE 2: VALUATION MODE ({ticker}) ---")
        
        # 1. LOAD DATA & ASSUMPTIONS
        master_data = load_local_data(ticker, output_folder)
        assumptions = load_user_assumptions(ticker, output_folder)
            
        if not master_data or not assumptions:
            print("❌ Error: Missing local data or assumptions. Run --mode setup first.")
            return

        # 2. RUN CORE DCF MATH
        from modeling.dcf import enterprise_value, run_sensitivity_analysis
            
        results = enterprise_value(
            master_data['income_statement'],
            master_data['cashflow_statement'],
            master_data['balance_statement'],
            period=int(assumptions['forecast_years']),
            discount_rate=assumptions['wacc'],
            earnings_growth_rate=assumptions['ebit_growth'],
            cap_ex_growth_rate=assumptions['capex_growth'],
            perpetual_growth_rate=assumptions['perpetual_growth']
        )

        # --- 3. EQUITY BRIDGE ---
        bal_stmt = master_data['balance_statement'][0]
        ev_stmt = master_data['enterprise_value_statement'][0]
            
        # Extract the key values
        debt = float(bal_stmt.get('totalDebt', 0))
        cash = float(bal_stmt.get('cashAndCashEquivalents', 0))
        
        # Get shares from the EV statement
        shares_outstanding = float(ev_stmt.get('numberOfShares', 0))
        
        # Calculate values
        equity_val = results['ev'] - debt + cash

        # SAFETY CHECK: Prevent dividing by zero
        if shares_outstanding > 0:
            intrinsic_price = equity_val / shares_outstanding
        else:
            print("⚠️ Warning: Could not find shares outstanding. Price set to 0.")
            intrinsic_price = 0

        # 4. GET MARKET PRICE AND DATE
        quote_data = master_data.get('quote', [])
        ev_data = master_data.get('enterprise_value_statement', [])
        
        market_price = 0.0
        price_source = "Not found"

        # Try live quote first
        if isinstance(quote_data, list) and len(quote_data) > 0:
            market_price = float(quote_data[0].get('price', 0))
            price_source = "Live Quote"
        
        # Fallback to last known price from EV statement
        if market_price == 0.0 and isinstance(ev_data, list) and len(ev_data) > 0:
            market_price = float(ev_data[0].get('stockPrice', 0))
            price_source = "Last Filing Data (Live Quote Restricted)"

        # 5. DISPLAY MAIN REPORT
        metadata = master_data.get('metadata', {})
        price_date = metadata.get('retrieved_at', 'Unknown')
        print("\n" + "="*45)
        print(f"  🏢 DCF VALUATION REPORT: {ticker}")
        print(f"  📅 Data Captured: {price_date}")
        print(f"  🔍 Price Source:  {price_source}") # Tells you where the price came from
        print("="*45)

        # This is the "Bridge" section
        print(f"  Enterprise Value:     ${results['ev']/1e9:.2f}B")
        print(f"  (+) Cash:             ${cash/1e9:.2f}B")
        print(f"  (-) Total Debt:       ${debt/1e9:.2f}B")
        print(f"  (=) Equity Value:     ${equity_val/1e9:.2f}B")
        print(f"  (/) Shares Out:       {shares_outstanding/1e6:.2f}M")
        print("-" * 45)

        print(f"  ✨ INTRINSIC PRICE:    ${intrinsic_price:.2f}")
        print(f"  📉 MARKET PRICE:       ${market_price:.2f}")
        
        # Calculate Upside/Downside
        if market_price > 0:
            upside = ((intrinsic_price / market_price) - 1) * 100
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
        with open(save_path, 'w', newline='') as f:
            # This line tells Excel: "Hey, I'm using commas!"
            f.write("sep=,\n") 
            
            upside_val = ((intrinsic_price / market_price) - 1) * 100 if market_price > 0 else 0
            f.write(f"Ticker,Intrinsic Price,Market Price,Upside %,Equity Value,EV,Debt,Cash\n")
            f.write(f"{ticker},{intrinsic_price:.2f},{market_price:.2f},{upside_val:.2f}%,{equity_val:.2f},{results['ev']:.2f},{debt:.2f},{cash:.2f}\n\n")
            f.write("--- SENSITIVITY ANALYSIS ---\n")
            
            # Save the dataframe below the summary
            sensitivity_df.to_csv(f, index=False)
            
        print(f"✅ Report saved to: {save_path}")

if __name__ == "__main__":
    main()
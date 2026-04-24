import os
import json
import argparse
# We import our specific "Department Heads"
from modeling.data import fetch_financials, convert_json_to_csv, create_assumption_template
from modeling.dcf import enterprise_value, load_user_assumptions

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--t', help='Stock Ticker', default='AAPL')
    parser.add_argument('--apikey', help='API Key', default=None)
    parser.add_argument('--mode', choices=['setup', 'run'], default='setup', 
                        help='setup: downloads data | run: calculates valuation')
    args = parser.parse_args()

    ticker = args.t.upper()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, "modeling", f"{ticker}_financials")

    # --- STAGE 1: SETUP ---
    if args.mode == 'setup':
        # 1. First, check if we have the key
        if not args.apikey:
            print("❌ ERROR: You must provide an --apikey to run 'setup' mode!")
            return # This exits the function early
        
        # 2. If we HAVE the key, continue with setup
        print(f"--- 🛠️ STAGE 1: SETUP MODE ({ticker}) ---")
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        master_data = fetch_financials(ticker, args.apikey)
        convert_json_to_csv(ticker) 
        create_assumption_template(ticker, output_folder)
        
        print(f"\n✅ Setup Complete! Now go to {output_folder}")
        print(f"👉 Edit '{ticker}_assumptions.csv' and save your changes.")
        print(f"🚀 When ready, run: python run_my_dcf.py --t {ticker} --mode run")

    # --- STAGE 2: RUN ---
    elif args.mode == 'run':
        print(f"--- 🧮 STAGE 2: VALUATION MODE ({ticker}) ---")
        
        json_path = os.path.join(script_dir, "modeling", "data.json")
        with open(json_path, 'r') as f:
            master_data = json.load(f)

        assumptions = load_user_assumptions(ticker, output_folder)

        if assumptions:
            # 1. Run the Math Engine (Calculates the value of the operations)
            results = enterprise_value(
                master_data['income_statement'],
                master_data['cashflow_statement'],
                master_data['balance_statement'],
                period=int(assumptions['forecast_years']),
                discount_rate=float(assumptions['wacc']),
                earnings_growth_rate=float(assumptions['ebit_growth']),
                cap_ex_growth_rate=float(assumptions['capex_growth']),
                perpetual_growth_rate=float(assumptions['perpetual_growth'])
            )

            # 2. THE EQUITY BRIDGE
            bal_stmt = master_data['balance_statement'][0] # Source of Truth for Debt/Cash
            ev_stmt = master_data['enterprise_value_statement'][0] # Source of Truth for Shares
            # Pull from Balance Sheet
            debt = float(bal_stmt.get('totalDebt', 0))
            cash = float(bal_stmt.get('cashAndCashEquivalents', 0))
        
            # Pull from EV Statement
            shares = float(ev_stmt.get('numberOfShares', 1))
        
            # Calculate
            equity_val = results['ev'] - debt + cash
            intrinsic_price = equity_val / shares
            
            # 3. SAVE THE FINAL REPORT
            save_path = os.path.join(output_folder, f"valuation_output_{ticker}.csv")
            with open(save_path, 'w', newline='') as f:
                f.write("sep=,\n") # Fix for Polish Excel
                f.write(f"Ticker,{ticker}\n")
                f.write(f"Enterprise Value,{results['ev']:.2f}\n")
                f.write(f"Total Debt,{debt:.2f}\n")
                f.write(f"Cash & Equivalents,{cash:.2f}\n")
                f.write(f"Equity Value,{equity_val:.2f}\n")
                f.write(f"Shares Outstanding,{shares:.0f}\n")
                f.write(f"INTRINSIC SHARE VALUE,{intrinsic_price:.2f}\n\n")
                
                # Attach the year-by-year math
                results['projections'].to_csv(f, index=False)
            
            # 4. FINAL DISPLAY
            print("\n" + "="*45)
            print(f"  🏢 DCF VALUATION REPORT: {ticker}")
            print("="*45)
            print(f"  Enterprise Value:      ${results['ev']:,.2f}")
            print(f"  (-) Total Debt:        ${debt:,.2f}")
            print(f"  (+) Total Cash:        ${cash:,.2f}")
            print(f"  -------------------------------------------")
            print(f"  (=) Equity Value:      ${equity_val:,.2f}")
            print(f"  (/) Shares Out:        {shares/1e9:.2f} Billion")
            print(f"  ===========================================")
            print(f"  ✨ INTRINSIC PRICE:    ${intrinsic_price:,.2f}")
            print(f"  ===========================================")
            print(f"  Report saved to: {save_path}")

if __name__ == "__main__":
    main()
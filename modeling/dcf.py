import pandas as pd
import json
import os

# --- 1 THE MATH ENGINE ---

def ulFCF(ebit, tax_rate, da, cwc, capex):
    """Calculates Unlevered Free Cash Flow"""
    return ebit * (1 - tax_rate) + da - cwc - abs(capex)

# --- 2 CORE ENGINE ---
def enterprise_value(income_statement, cashflow_statement, balance_statement, period, discount_rate, earnings_growth_rate, cap_ex_growth_rate, perpetual_growth_rate):
    """Calculates Enterprise Value using DCF method"""
    
    # 1. Base Year Data (Year 0)
    revenue = float(income_statement[0].get('revenue', 0))
    ebit = float(income_statement[0].get('ebit', 0))
    
    tax_exp = float(income_statement[0].get('incomeTaxExpense', 0))
    ebt = float(income_statement[0].get('incomeBeforeTax', 1))
    tax_rate = tax_exp / ebt if ebt > 0 else 0.21
    
    da = float(cashflow_statement[0].get('depreciationAndAmortization', 0))
    capex = float(cashflow_statement[0].get('capitalExpenditure', 0))
    
    # Proxy for Change in Working Capital
    cwc = revenue * 0.01 

    projection_data = []
    pv_fcf_list = []

    # 2. Forecast Period (Stage 1)
    for yr in range(1, period + 1):
        yr_rev = revenue * ((1 + earnings_growth_rate) ** yr)
        yr_ebit = ebit * ((1 + earnings_growth_rate) ** yr)
        yr_da = da * ((1 + earnings_growth_rate) ** yr)
        yr_capex = capex * ((1 + cap_ex_growth_rate) ** yr)
        yr_cwc = cwc * ((1 + earnings_growth_rate) ** yr)
        
        fcf = ulFCF(yr_ebit, tax_rate, yr_da, yr_cwc, yr_capex)
        pv_fcf = fcf / ((1 + discount_rate) ** yr)
        
        pv_fcf_list.append(pv_fcf)
        projection_data.append({
            "Year": yr,
            "Revenue": round(yr_rev, 2),
            "EBIT": round(yr_ebit, 2),
            "EBIT_Margin_%": round((yr_ebit / yr_rev) * 100, 2) if yr_rev > 0 else 0,
            "FCF": round(fcf, 2),
            "PV_of_FCF": round(pv_fcf, 2)
        })

    # 3. Terminal Value (Stage 2)
    final_fcf = projection_data[-1]["FCF"]
    terminal_value = (final_fcf * (1 + perpetual_growth_rate)) / (discount_rate - perpetual_growth_rate)
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** period)
    
    total_ev = sum(pv_fcf_list) + pv_terminal_value
    
    return {
        "ev": total_ev,
        "projections": pd.DataFrame(projection_data),
        "tv_pct": (pv_terminal_value / total_ev) * 100
    }
# --- 3 SENSITIVITY ENGINE ---
def run_sensitivity_analysis(income_stmt, cash_stmt, balance_stmt, assumptions, debt, cash, shares):
    """
    Runs multiple DCF scenarios by varying WACC and Perpetual Growth.
    Returns a DataFrame grid of share prices.
    """
    # 1. Define the ranges (Current, -1%, +1% for WACC | Current, -0.5%, +0.5% for Growth)
    wacc_range = [round(assumptions['wacc'] - 0.01, 3), 
                  round(assumptions['wacc'], 3), 
                  round(assumptions['wacc'] + 0.01, 3)]
    
    growth_range = [round(assumptions['perpetual_growth'] - 0.005, 3), 
                    round(assumptions['perpetual_growth'], 3), 
                    round(assumptions['perpetual_growth'] + 0.005, 3)]
    
    results_grid = []

    # 2. Nested loop to calculate every combination
    for w in wacc_range:
        row = {"WACC / Growth": f"{w*100:.1f}%"}
        for g in growth_range:
            # Re-run the core math engine for each scenario
            res = enterprise_value(
                income_stmt, cash_stmt, balance_stmt,
                period=int(assumptions['forecast_years']),
                discount_rate=w,
                earnings_growth_rate=assumptions['ebit_growth'],
                cap_ex_growth_rate=assumptions['capex_growth'],
                perpetual_growth_rate=g
            )
            # Calculate price using the Equity Bridge
            price = (res['ev'] - debt + cash) / shares
            row[f"{g*100:.1f}%"] = round(price, 2)
        
        results_grid.append(row)

    # 3. Convert list of dicts to a clean table
    return pd.DataFrame(results_grid)

# --- 4 DATA LOADERS ---
def load_user_assumptions(ticker, folder):
    """The Smart Socket for Polish Excel Files"""
    path = os.path.join(folder, f"{ticker}_assumptions.csv")
    if not os.path.exists(path):
        print(f"❌ Error: {path} not found.")
        return None
    
    try:
        # Detects semicolon automatically and doesn't skip header
        df = pd.read_csv(path, sep=None, engine='python')
        df.columns = df.columns.str.strip()
        
        # Convert Polish commas to dots if necessary
        if df['Value'].dtype == 'object':
            df['Value'] = df['Value'].str.replace(',', '.').astype(float)
        
        return dict(zip(df['Assumption'], df['Value']))
    except Exception as e:
        print(f"❌ Error reading assumptions: {e}")
        return None

# --- 5 EXECUTION BLOCK ---

if __name__ == "__main__":
    ticker = 'AMZN'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(script_dir, f"{ticker}_financials")

    a = load_user_assumptions(ticker, folder)

    if a:
        with open(os.path.join(script_dir, 'data.json'), 'r') as f:
            master_data = json.load(f)

        results = enterprise_value(
            master_data['income_statement'],
            master_data['cashflow_statement'],
            master_data['balance_statement'],
            period=int(a['forecast_years']),
            discount_rate=a['wacc'],
            earnings_growth_rate=a['ebit_growth'],
            cap_ex_growth_rate=a['capex_growth'],
            perpetual_growth_rate=a['perpetual_growth']
        )

        # Equity Bridge
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
        
        # Save Report
        save_path = os.path.join(folder, f"valuation_output_{ticker}.csv")
        with open(save_path, 'w', newline='') as f:
            f.write("sep=,\n")
            f.write(f"Intrinsic Price,{intrinsic_price:.2f}\n") # <--- Fixed name
            f.write(f"TV Contribution,{results['tv_pct']:.2f}%\n\n")
            results['projections'].to_csv(f, index=False)
        
        print(f"✅ Analysis complete for {ticker}")
        print(f"   Intrinsic Value: ${intrinsic_price:.2f}") # <--- Fixed name
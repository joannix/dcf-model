import pandas as pd
import json
import os

# --- 1 THE MATH ENGINE ---

def ulFCF(ebit, tax_rate, da, cwc, capex):
    """Calculates Unlevered Free Cash Flow"""
    return ebit * (1 - tax_rate) + da - cwc - abs(capex)

# --- 2 CORE ENGINE ---
def enterprise_value(income_statement, cashflow_statement, balance_statement, period, discount_rate, earnings_growth_rate, cap_ex_growth_rate, perpetual_growth_rate, assumptions):
    """Calculates Enterprise Value using DCF method"""
    
    # 1. Base Metrics (Fixing Order: Define variables before using them)
    base_revenue = float(income_statement[0].get('revenue', 0))
    base_ebit = float(income_statement[0].get('ebit', 0))
    base_margin = base_ebit / base_revenue if base_revenue > 0 else 0.1
    
    # Define ebt and tax_exp BEFORE calculating tax_rate
    ebt = float(income_statement[0].get('incomeBeforeTax', 1))
    tax_exp = float(income_statement[0].get('incomeTaxExpense', 0))
    tax_rate = tax_exp / ebt if ebt > 0 else 0.21
    
    da = float(cashflow_statement[0].get('depreciationAndAmortization', 0))
    capex = float(cashflow_statement[0].get('capitalExpenditure', 0))
       
    # Use base_revenue (not revenue) for CWC proxy
    cwc_base = base_revenue * 0.01 

    projection_data = []
    pv_fcf_list = []

    # 2. History & Margin Logic
    hist_ebit = [float(item.get('ebit', 0)) for item in reversed(income_statement[:5])]
    hist_years = [item.get('date')[:4] for item in reversed(income_statement[:5])]
    
    # Use the delta from assumptions
    margin_delta = assumptions.get('ebit_margin_delta', 0)
    forecast_margin = base_margin + margin_delta

    for yr in range(1, period + 1):
        # Using revenue_growth from assumptions
        rev_growth = assumptions.get('revenue_growth', earnings_growth_rate)
        yr_rev = base_revenue * ((1 + rev_growth) ** yr)
        
        yr_ebit = yr_rev * forecast_margin
        
        # Keep DA and CapEx scaling with revenue growth
        yr_da = da * ((1 + rev_growth) ** yr)
        yr_capex = capex * ((1 + cap_ex_growth_rate) ** yr)
        yr_cwc = cwc_base * ((1 + rev_growth) ** yr)
        
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
    
    pv_sum_of_forecast = sum(pv_fcf_list)
    
    final_enterprise_value = pv_sum_of_forecast + pv_terminal_value
    
    # PREPARE LISTS FOR CHARTS
    fcf_only_list = [item["FCF"] for item in projection_data]
    years_labels = [f"Year {item['Year']}" for item in projection_data]

    return {
        "ev": final_enterprise_value,
        "projections": pd.DataFrame(projection_data),
        "tv_pct": (pv_terminal_value / final_enterprise_value) * 100 if final_enterprise_value != 0 else 0,
        "years": years_labels,
        "fcf_projections": fcf_only_list,
        "pv_sum": pv_sum_of_forecast,
        "pv_tv": pv_terminal_value,
        "ebit_history": hist_ebit,
        "ebit_hist_years": hist_years,
        "ebit_forecast": [item["EBIT"] for item in projection_data],
        "ebit_forecast_years": [f"{int(hist_years[-1])+i}E" for i in range(1, period+1)]
    }

# --- 3 SENSITIVITY ENGINE ---
def run_sensitivity_analysis(income_statement, cashflow_statement, balance_statement, assumptions, debt, cash, shares):
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
            res = enterprise_value(
                income_statement, 
                cashflow_statement, 
                balance_statement,
                int(assumptions['forecast_years']),   # period
                w,                                    # discount_rate
                assumptions.get('revenue_growth', 0.05), # earnings_growth_rate
                assumptions.get('capex_growth', 0.05),   # cap_ex_growth_rate
                g,                                    # perpetual_growth_rate
                assumptions                           # the actual dictionary
            )
            
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
    
    display_name = ticker # Default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if "Company Name" in first_line:
                # Splits "Company Name;The Boeing Company" and takes the second part
                display_name = first_line.split(';')[1].strip()
    except Exception as e:
        print(f"⚠️ Could not read display name from header: {e}")
        
    try:
        # Detects semicolon automatically and skips header
        df = pd.read_csv(path, skiprows=3, sep=';', engine='python')
        df.columns = df.columns.str.strip()
        
        # Convert Polish commas to dots if necessary
        if df['Value'].dtype == 'object':
            df['Value'] = df['Value'].str.replace(',', '.').astype(float)
        
        assumptions_dict = dict(zip(df['Assumption'], df['Value']))
        
        # 🛡️ THE FIX: Add the name we found earlier to this dictionary
        assumptions_dict['company_full_name'] = display_name
        
        return assumptions_dict
    
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
            earnings_growth_rate=a.get('revenue_growth', 0.05),
            cap_ex_growth_rate=a['capex_growth'],
            perpetual_growth_rate=a['perpetual_growth'],
            assumptions=a
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
       
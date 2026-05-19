import pandas as pd
import json
import os

# --- 1 THE MATH ENGINE ---

def ulFCF(yr_ebit, yr_tax_payment, yr_da, yr_cwc, yr_capex):
    """Calculates Unlevered Free Cash Flow"""
    return yr_ebit - yr_tax_payment + yr_da - yr_cwc - yr_capex

#--- THE HELPER ---
def get_dynamic_assumption(row_data, current_year, default_val):
    """Iterates from Year 1 up to current year to handle step changes and forward-filling"""
    last_valid_val = default_val
    
    if not isinstance(row_data, dict):
        return default_val

    for y in range(1, current_year + 1):
        step_val = row_data.get(f"Year {y}")
        # Check for both empty strings and NaN values safely
        if step_val is not None and str(step_val).strip() != "" and not pd.isna(step_val):
            try:
                last_valid_val = float(str(step_val).replace(',', '.'))
            except ValueError:
                pass
                
    return last_valid_val

# --- 2 CORE ENGINE ---
def enterprise_value(income_statement, cashflow_statement, balance_statement, period, discount_rate, earnings_growth_rate, capex_growth_rate, perpetual_growth_rate, assumptions):
    """Calculates Enterprise Value using DCF method over a dynamic time horizon"""
    
    projection_data = []
    pv_fcf_list = []

    # 1. Establish the Anchor Year from the latest Income Statement entry
    latest_inc_entry = income_statement[0]
    target_year = latest_inc_entry.get('calendarYear')
    
    # Base Income Statement Metrics
    base_revenue = float(latest_inc_entry.get('revenue', 0))
    base_ebit = float(latest_inc_entry.get('ebit', 0))
    base_margin = base_ebit / base_revenue if base_revenue > 0 else 0.0
    
    tax_exp_entry = next((item for item in income_statement if item.get('calendarYear') == target_year), latest_inc_entry)
    tax_exp = float(tax_exp_entry.get('incomeTaxExpense', 0))
    raw_tax_rate = tax_exp / base_ebit if base_ebit > 0 else 0.21
    tax_rate = min(max(raw_tax_rate, 0.15), 0.25)
    
    # 4. Extract Cash Flow Metrics
    latest_cf_entry = next((item for item in cashflow_statement if item.get('calendarYear') == target_year), cashflow_statement[0])
    da = abs(float(latest_cf_entry.get('depreciationAndAmortization', 0)))
    capex = abs(float(latest_cf_entry.get('capitalExpenditure', 0)))
    da_catchup = 0.10
    
    # Extract dynamic horizon from assumptions file safely
    forecast_years = int(period)

    # Core forecasting loop using dynamic step assumptions
    for yr in range(1, forecast_years + 1):
        rev_row = assumptions.get('revenue_growth', {})
        margin_row = assumptions.get('ebit_margin_delta', {})
        capex_row = assumptions.get('capex_delta', {})

        try:
            default_rev = float(str(rev_row.get('Default', 0.05)).replace(',', '.'))
            default_margin = float(str(margin_row.get('Default', 0.0)).replace(',', '.'))
            default_capex = float(str(capex_row.get('Default', 0.0)).replace(',', '.'))
        except ValueError:
            default_rev, default_margin, default_capex = 0.05, 0.0, 0.0

        rev_growth = get_dynamic_assumption(rev_row, yr, default_rev)
        margin_delta = get_dynamic_assumption(margin_row, yr, default_margin)
        capex_delta = get_dynamic_assumption(capex_row, yr, default_capex)

        # Compound revenue, apply structural margin adjustments
        prev_rev = base_revenue if yr == 1 else projection_data[-1]["Revenue"]
        yr_rev = prev_rev * (1 + rev_growth)
        yr_ebit = yr_rev * (base_margin + margin_delta)
        yr_tax_payment = max(0, yr_ebit * tax_rate)
        yr_ebit_after_tax = yr_ebit - yr_tax_payment
        prev_capex = capex if yr == 1 else projection_data[-1]["CapEx"]
        yr_capex = prev_capex * (1 + rev_growth + capex_delta)
                
        yr_cwc = (yr_rev - prev_rev) * 0.10
        prev_da = da if yr == 1 else projection_data[-1]["D&A"]
        yr_da = (prev_da * (1 + rev_growth)) + (yr_capex * da_catchup * (yr / forecast_years))
            
        fcf = ulFCF(yr_ebit, yr_tax_payment, yr_da, yr_cwc, yr_capex)
        pv_fcf = fcf / ((1 + discount_rate) ** yr)
        
        pv_fcf_list.append(pv_fcf)
        projection_data.append({
            "Year": yr,
            "Revenue": yr_rev,
            "EBIT": yr_ebit,
            "EBIT_After_Tax": yr_ebit_after_tax,
            "CapEx": yr_capex,
            "D&A": yr_da,
            "NWC_Change": yr_cwc,
            "FCF": fcf,
            "PV_of_FCF": pv_fcf
        })
 
    # Terminal Value Calculation
    final_fcf = projection_data[-1]["FCF"]
    terminal_value = (final_fcf * (1 + perpetual_growth_rate)) / (discount_rate - perpetual_growth_rate)
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** forecast_years)
    
    pv_sum_of_forecast = sum(pv_fcf_list)
    final_enterprise_value = pv_sum_of_forecast + pv_terminal_value
    if final_enterprise_value < 0:
        final_enterprise_value = 0.0
    
    # Prepare historical data frames for frontend components
    fcf_only_list = [item["FCF"] for item in projection_data]
    years_labels = [f"Year {item['Year']}" for item in projection_data]
    hist_ebit = [float(item.get('ebit', 0)) for item in reversed(income_statement[:5])]
    hist_years = [str(item.get('date', '0000'))[:4] for item in reversed(income_statement[:5])]

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
        "ebit_forecast_years": [f"{int(hist_years[-1])+i}E" if hist_years else f"Yr{i}E" for i in range(1, forecast_years + 1)]
    }

def check_model_integrity(projection_data):
    """Checks if the DCF assumptions lead to a 'broken' business case"""
    negative_fcf_years = [item['Year'] for item in projection_data if item['FCF'] < 0]
    
    if len(negative_fcf_years) == len(projection_data):
        print("⚠️ WARNING: FCF is negative throughout the entire forecast. DCF may not be appropriate.")
    elif len(negative_fcf_years) > (len(projection_data) / 2):
        print(f"💡 NOTE: Company is FCF negative for {len(negative_fcf_years)} years. Check turnaround realities.")

# --- 3 SENSITIVITY ENGINE ---
def run_sensitivity_analysis(income_statement, cashflow_statement, balance_statement, assumptions, debt, cash, shares):
    """Runs multiple DCF scenarios by varying WACC and Perpetual Growth variables safely"""
    try:
        base_wacc = float(str(assumptions.get('wacc', {}).get('Default', 0.085)).replace(',', '.'))
        base_g = float(str(assumptions.get('perpetual_growth', {}).get('Default', 0.02)).replace(',', '.'))
        forecast_years = int(float(assumptions.get('forecast_years', {}).get('Default', 5)))
    except (ValueError, TypeError):
        base_wacc, base_g, forecast_years = 0.085, 0.02, 5

    wacc_range = [round(base_wacc - 0.01, 3), round(base_wacc, 3), round(base_wacc + 0.01, 3)]
    growth_range = [round(base_g - 0.005, 3), round(base_g, 3), round(base_g + 0.005, 3)]
    
    results_grid = []

    for w in wacc_range:
        row = {"WACC / Growth": f"{w*100:.1f}%"}
        for g in growth_range:
            res = enterprise_value(
                income_statement=income_statement, 
                cashflow_statement=cashflow_statement, 
                balance_statement=balance_statement,
                period=forecast_years,
                discount_rate=w,
                earnings_growth_rate=assumptions.get('revenue_growth', {}),
                capex_growth_rate=assumptions.get('capex_delta', {}),
                perpetual_growth_rate=g,
                assumptions=assumptions
            )
            
            price = (res['ev'] - debt + cash) / shares if shares > 0 else 0.0
            row[f"{g*100:.1f}%"] = round(price, 2)
        
        results_grid.append(row)

    return pd.DataFrame(results_grid)

# --- 4 DATA LOADERS ---
def load_user_assumptions(ticker, folder):
    """The Wide Matrix Loader for Horizontal 10-Year DCF Spreadsheets"""
    path = os.path.join(folder, f"{ticker}_assumptions.csv")
    if not os.path.exists(path):
        print(f"❌ Error: {path} not found.")
        return None
    
    display_name = ticker
    try:
        with open(path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if "Company Name" in first_line:
                display_name = first_line.split(';')[1].strip()
    except Exception as e:
        print(f"⚠️ Could not read display name from header: {e}")
        
    try:
        df = pd.read_csv(path, skiprows=3, sep=';', engine='python')
        df.columns = df.columns.str.strip()
        
        df['Assumption'] = df['Assumption'].str.strip()
        df.set_index("Assumption", inplace=True)
        
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                # Try to safely cast numeric columns back to float values
                df[col] = pd.to_numeric(df[col], errors='ignore')

        assumptions_dict = df.to_dict(orient="index")
        assumptions_dict['company_full_name'] = display_name
        
        return assumptions_dict
    
    except Exception as e:
        print(f"❌ Error reading assumptions matrix: {e}")
        return None
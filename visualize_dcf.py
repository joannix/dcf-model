import os
import sys
import json
import argparse
import pandas as pd
import matplotlib.pyplot as plt

def get_output_path(ticker):
    """Creates a ticker-specific subfolder inside visualizations."""
    base_dir = "visualizations"
    ticker_dir = os.path.join(base_dir, ticker.upper())
    if not os.path.exists(ticker_dir):
        os.makedirs(ticker_dir)
    return ticker_dir

def save_projections(ticker, years, flows):
    ticker_dir = get_output_path(ticker)
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = ['#2ecc71' if cf > 0 else '#e74c3c' for cf in flows]
    bars = ax.bar(years, flows, color=colors, alpha=0.8)
    
    ax.set_title(f'Projected Free Cash Flows: {ticker}', fontsize=14, fontweight='bold')
    ax.set_ylabel('USD ($)')
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval, f'${yval:,.0f}', 
                va='bottom', ha='center', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(ticker_dir, "projections.png"), dpi=300)
    plt.close()

def save_valuation_bridge(ticker, pv_forecast, pv_tv, cash, debt):
    ticker_dir = get_output_path(ticker)
    ev = pv_forecast + pv_tv
    equity_value = ev + cash - debt
    
    labels = ['PV Forecast', 'PV Terminal Value', 'Cash (+)', 'Debt (-)', 'Equity Value']
    values = [pv_forecast, pv_tv, cash, -debt, equity_value]
    
    step_values = [0] * len(values)
    current = 0
    for i in range(len(values)):
        if i == 0 or i == len(values) - 1:
            step_values[i] = 0
        else:
            step_values[i] = current
        current += values[i]

    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ['#5dade2', '#2e86c1', '#2ecc71', '#e74c3c', '#9b59b6']
    ax.bar(labels, values, bottom=step_values, color=colors)
    
    for i, v in enumerate(values):
        label_pos = step_values[i] + v if v >= 0 else step_values[i]
        ax.text(i, label_pos, f'${abs(v):,.0f}', 
                ha='center', va='bottom' if v >= 0 else 'top', fontweight='bold')

    ax.set_title(f'Valuation Bridge: {ticker}\n(Total EV: ${ev:,.0f})', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(ticker_dir, "valuation_bridge.png"), dpi=300)
    plt.close()

def save_ebit_chart(ticker, hist_years, hist_ebit, fore_years, fore_ebit):
    plt.figure(figsize=(10, 6))
    
    # Combine data
    all_years = hist_years + fore_years
    all_ebit = [x/1e9 for x in hist_ebit] + [x/1e9 for x in fore_ebit]
    
    # Color history differently than forecast
    colors = ['#2c3e50'] * len(hist_years) + ['#3498db'] * len(fore_years)
    
    plt.bar(all_years, all_ebit, color=colors)
    plt.title(f"{ticker}: Historical & Forecasted EBIT", fontsize=14)
    plt.ylabel("EBIT (Billions $)")
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    output_dir = f"visualizations/{ticker}"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(f"{output_dir}/{ticker}_ebit_trend.png")
    plt.close()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--t", type=str, required=True)
    args = parser.parse_args()
    ticker = args.t.upper()

    path = os.path.join("output", ticker, "chart_data.json")
    
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        
        print(f"✅ Real data loaded for {ticker}")

        save_projections(
            ticker, 
            data['forecast_years'], 
            data['forecast_fcf']
        )
        
        save_valuation_bridge(
            ticker, 
            data['pv_forecast_sum'], 
            data['pv_terminal_value'], 
            data['cash'], 
            data['debt']
        )
        
        print(f"🚀 Success! Charts generated for {ticker} in /visualizations")
        
    else:
        print(f"❌ No data found for {ticker}. Run the valuation first.")
        # Optional: exit the script so it doesn't try to continue
        sys.exit(1) 
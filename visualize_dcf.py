import os
import sys
import json
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def get_output_path(ticker):
    """Creates a ticker-specific subfolder inside visualizations."""
    base_dir = "visualizations"
    ticker_dir = os.path.join(base_dir, ticker.upper())
    if not os.path.exists(ticker_dir):
        os.makedirs(ticker_dir)
    return ticker_dir

def style_financial_chart(ax, title, ylabel):
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_xlabel("Year", fontsize=12)
    sns.despine() # Removes the top and right border lines
    plt.tight_layout()

def plot_ebit_growth(ticker, hist_years, hist_ebit, fore_years, fore_ebit):
    sns.set_theme(style="darkgrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    
    all_years = hist_years + fore_years
    all_ebit = [(x / 1e9) for x in (hist_ebit + fore_ebit)]
    
    colors = ['#2c3e50'] * len(hist_years) + ['#3498db'] * len(fore_years)
    
    sns.barplot(x=all_years, y=all_ebit, hue=all_years, palette=colors, legend=False, ax=ax)
    
    style_financial_chart(ax, f"{ticker}: Historical & Forecasted EBIT", "EBIT (Billions $)")
    
    plt.savefig(os.path.join(get_output_path(ticker), "ebit_growth.png"), dpi=300)
    plt.close()

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

def plot_price_vs_target(ticker, historical_prices, target_price):
    """
    Visualizes the stock's historical journey compared to the intrinsic price.
    """
    if not historical_prices:
        return
    
    sns.set_theme(style="darkgrid")
    plt.figure(figsize=(10, 6))
    
    # 1. Parse the JSON list of dicts into dates and prices
    dates = [pd.to_datetime(item['date']) for item in historical_prices]
    prices = [item['close'] for item in historical_prices]
    
    # 2. Plot historical market line using true dates for the X-axis
    plt.plot(dates, prices, label='Market Price', color='royalblue', linewidth=2)
    
    # 3. Plot horizontal "Intrinsic Value" line across the time horizon
    plt.axhline(y=target_price, color='crimson', linestyle='--', label=f'Target: ${target_price:.2f}')
    
    plt.title(f"${ticker} Market History vs. DCF Intrinsic Value", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Price ($)", fontsize=12)
    
    # Clean up the date labels on X-axis so they don't overlap
    plt.gcf().autofmt_xdate() 
    plt.legend()

    plt.savefig(os.path.join(get_output_path(ticker), "market_comparison.png"), dpi=300)
    plt.close()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--t", type=str, required=True)
    args = parser.parse_args()
    ticker = args.t.upper()

    path = os.path.join("output", ticker, "chart_data.json")
    
    if os.path.exists(path):
        ticker_dir = get_output_path(ticker)
        for f in os.listdir(ticker_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(ticker_dir, f))

        with open(path, 'r') as f:
            data = json.load(f)
        
        print(f"✅ Real data loaded for {ticker}")

        forecast_years_list = data.get('ebit_forecast_years', [])
        
        if 'projections' in data:
            forecast_fcf_list = [row['FCF'] for row in data['projections']]
        else:
            forecast_fcf_list = []

        forecast_years_list = [str(y).replace('E', '') for y in forecast_years_list]
        
        save_projections(ticker, forecast_years_list, forecast_fcf_list)
        
        save_valuation_bridge(ticker, data['pv_forecast_sum'], data['pv_terminal_value'], data['cash'], data['debt'])
        
        plot_ebit_growth(
            ticker, 
            data.get('ebit_hist_years', []), 
            data.get('ebit_history', []), 
            data.get('ebit_forecast_years', []), 
            data.get('ebit_forecast', [])
        )

        if 'price_history' in data:
            plot_price_vs_target(
                data['ticker'], 
                data['price_history'], 
                data['intrinsic_price'], 
            )
                   
        print(f"🚀 Success! Charts generated for {ticker} in /visualizations/{ticker}")
        
    else:
        print(f"❌ No data found for {ticker}. Run the valuation first.")
        sys.exit(1)
        
import matplotlib.pyplot as plt
import os
import sys

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

if __name__ == "__main__":
    ticker_input = sys.argv[1].upper() if len(sys.argv) > 1 else "SAMPLE"
    
    # Cleaned up Mock Data
    mock_years = ["2026E", "2027E", "2028E", "2029E", "2030E"]
    mock_flows = [1200, 1450, 1700, 1950, 2200]
    
    pv_fcff_sum = 3000   
    pv_terminal = 12000  
    cash_on_hand = 2000
    total_debt = 3500
    
    save_projections(ticker_input, mock_years, mock_flows)
    save_valuation_bridge(ticker_input, pv_fcff_sum, pv_terminal, cash_on_hand, total_debt)
    print(f"🚀 Success! Charts generated for {ticker_input} in /visualizations")
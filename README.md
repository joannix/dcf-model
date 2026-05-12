# 📈 Financial DCF Valuation Engine

A modular Python tool to automate Discounted Cash Flow valuations using the Financial Modeling Prep API.

### 🔬 Valuation Methodology

The engine utilizes an **Unlevered Free Cash Flow (uFCF)** approach to determine Enterprise Value.

The uFCF Formula:

$$
uFCF = (EBIT \times (1 - t)) + DA - \Delta NWC - CapEx
$$

Where:
* **Revenue Projection**: Forecasted based on the `revenue_growth` percentage in your CSV.
* **EBIT (Operating Income)**: Calculated using a "Step-Up" margin approach:
    $$Forecast\ Margin = Historical\ Base\ Margin + Margin\ Delta$$
    This allows the user to model operational improvements (efficiency gains) or headwinds over the forecast period.
* **Tax Rate (t)**: Calculated as a historical effective rate ($Income\ Tax\ Expense / EBT$).
* **D&A & NWC**: Scaled inline with **Revenue Growth** to maintain operational intensity.
* **CapEx**: Scaled independently using the specific `capex_growth` assumption, allowing for modeling of capital-heavy expansion or maintenance-only phases.

#### Terminal Value:
We apply the **Gordon Growth Method** to the final projected year:
$$TV = \frac{FCF_{n} \times (1 + g)}{(WACC - g)}$$

## 🚀 Key Features
* **Automated Data Fetching**: Pulls Income Statements, Balance Sheets, and Cash Flows.
* **Equity Bridge**: Moves from Enterprise Value to Equity Value by adjusting for Debt and Cash.
* **Visualization Suite**: Generates Bar Charts for Cash Flows and Waterfall Charts for Valuation Bridges.
* **Resilient Logic**: Automatic fallback to filing data if live quotes are restricted.

## 📂 Project Structure
Data is organized by ticker within the output directory:
- `output/<ticker>/data.json` — Raw API response
- `output/<ticker>/assumptions_<ticker>.csv` — **User-editable** inputs
- `output/<ticker>/valuation_output_<ticker>.csv` — Final report
Charts are organized by ticker within the visualizations directory:
- `visualizations/<ticker>/projections.png` — Bar Charts for Cash Flows
- `visualizations/<ticker>/valuation_bridge.png` — Waterfall Chart for Valuation Bridge

## ⚙️ Configuration
To keep your credentials secure, this engine uses a `.env` file.

1. Create a file named `.env` in the root directory.
2. Add your Financial Modeling Prep API key:
    ``plaintext
    FMP_API_KEY=your_actual_key_here

The Python script will automatically load this key from the environment.

## 🛠️ How to Run

Follow these three steps to generate a valuation:

1. **Initialize & Fetch Data**:
   Download the latest financials and generate the assumptions template for a specific ticker:
   ```powershell
   python run_my_dcf.py --t <ticker> --mode setup

2. **Configure Assumptions***:
    Open the generated CSV file located at:
    output/<ticker>/assumptions_<ticker>.csv

3. **Execute Valuation**:
    Calculate the intrinsic value based on your custom assumptions:
    ```powershell
    python run_my_dcf.py --t <ticker> --mode run

4. **Create Charts**:
    ```powershell
    python visualize_dcf.py --t <ticker>
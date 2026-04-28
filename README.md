# 📈 Financial DCF Valuation Engine

A modular Python tool to automate Discounted Cash Flow valuations using the Financial Modeling Prep API.

### 🔬 Valuation Methodology

The engine utilizes an **Unlevered Free Cash Flow (uFCF)** approach to determine Enterprise Value.

The uFCF Formula:

$$
uFCF = (EBIT \times (1 - t)) + DA - \Delta NWC - CapEx
$$

Where:
* **EBIT**: Earnings Before Interest and Taxes.
* **t**: Effective Tax Rate (calculated as `incomeTaxExpense / incomeBeforeTax`).
* **D&A**: Depreciation and Amortization (Non-cash expenses).
* **$\Delta$ NWC**: Change in Working Capital (Impact of short-term assets/liabilities).
* **CapEx**: Capital Expenditure (Investment in long-term assets).

#### Terminal Value:
We apply the **Gordon Growth Method** to the final projected year:
$$TV = \frac{FCF_{n} \times (1 + g)}{(WACC - g)}$$

## 🚀 Key Features
* **Automated Data Fetching**: Pulls Income Statements, Balance Sheets, and Cash Flows.
* **Equity Bridge**: Moves from Enterprise Value to Equity Value by adjusting for Debt and Cash.
* **Resilient Logic**: Automatic fallback to filing data if live quotes are restricted.
* **Auto-Organized**: Dynamically creates folders for each ticker.

## 📂 Project Structure
Data is organized by ticker within the output directory:
- `output/<ticker>/data.json` — Raw API response
- `output/<ticker>/assumptions_<ticker>.csv` — **User-editable** inputs
- `output/<ticker>/valuation_output_<ticker>.csv` — Final report

## 🛠️ How to Run

Follow these three steps to generate a valuation:

1. **Initialize & Fetch Data**:
   Download the latest financials and generate the assumptions template for a specific ticker:
   ```powershell
   python run_my_dcf.py --t KO --mode setup --apikey YOUR_API_KEY

2. Configure Assumptions:
    Open the generated CSV file located at:
    output/<ticker>/assumptions_<ticker>.csv

3. Execute Valuation:
    Calculate the intrinsic value based on your custom assumptions:
    ```powershell
    python run_my_dcf.py --t KO --mode run





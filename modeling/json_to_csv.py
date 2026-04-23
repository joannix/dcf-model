import json
import pandas as pd
import os

def convert_json_to_csv(ticker):
    print(f"DEBUG: Function called with ticker: {ticker}")
    # 1. Setup Folders
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'data.json')
    
    # Create a subfolder for this specific ticker
    output_folder = os.path.join(script_dir, f"{ticker}_financials")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    try:
        with open(json_path, 'r') as f:
            master_data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: data.json not found!")
        return

    for statement_name, data in master_data.items():
        if data: 
            # Convert list of dictionaries to a DataFrame
            df = pd.DataFrame(data)
            
            # Set 'date' as the index so years become headers after transposing
            if 'date' in df.columns:
                df.set_index('date', inplace=True)
            
            # This was the missing line! It flips the table.
            df_transposed = df.transpose()
            
            csv_path = os.path.join(output_folder, f"{statement_name}.csv")
            
            # The 'with' block for the Excel-friendly format
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                f.write("sep=,\n") # Tells Excel to use commas
                df_transposed.to_csv(f, index=True)
            
            print(f"✅ Saved Transposed: {csv_path}")

if __name__ == "__main__":
    current_ticker = 'AMZN' 
    convert_json_to_csv(current_ticker)
import pandas as pd

file_path = r"C:\Users\ruchi\OneDrive\University of Washington\Research\Bio Arm\neb_table.html"

# Extract all tables from the HTML file
tables = pd.read_html(file_path)

print("Tables found:", len(tables))

# Usually the main table is the first one
df = tables[0]

# Export to JSON
df.to_json("neb_restriction_enzymes.json",
           orient="records",
           indent=2)

print("JSON saved!")
print(df.head())
import os
print("Saved to:", os.getcwd())
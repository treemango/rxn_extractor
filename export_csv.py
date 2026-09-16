import csv
import json
import os

input_file = "data/experiments.csv"
output_file = "data/flattened_results.csv"

if not os.path.exists(input_file):
    print(f"Error: {input_file} not found.")
    exit(1)

with open(input_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

flattened_rows = []
all_keys = set(["paper_identifier", "experiment_number", "overall_confidence"])

for row in rows:
    flat = {
        "paper_identifier": row.get("paper_identifier"),
        "experiment_number": row.get("experiment_number"),
        "overall_confidence": row.get("overall_confidence")
    }
    
    # Parse the JSON data column
    try:
        data = json.loads(row.get("data", "{}"))
        # The JSON contains sub-domains like "catalyst", "conditions", etc.
        for domain_name, domain_data in data.items():
            if domain_data:
                for k, v in domain_data.items():
                    # Prefix column names with domain, e.g., "conditions_temperature"
                    col_name = f"{domain_name}_{k}"
                    flat[col_name] = v
                    all_keys.add(col_name)
    except Exception as e:
        pass
        
    flattened_rows.append(flat)

# Write to new CSV
fieldnames = sorted(list(all_keys))
with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flattened_rows)

print(f"Successfully flattened {len(flattened_rows)} experiments!")
print(f"Saved to: {output_file}")


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
# Base columns we always want first
base_columns = ["paper_identifier", "experiment_number", "overall_confidence"]
all_keys = set(base_columns)

for row in rows:
    flat = {
        "paper_identifier": row.get("paper_identifier"),
        "experiment_number": row.get("experiment_number"),
        "overall_confidence": row.get("overall_confidence")
    }
    
    try:
        data = json.loads(row.get("data", "{}"))
        
        # The actual extracted fields are nested inside "sub_domain_results"
        sub_domain_results = data.get("sub_domain_results", {})
        
        for domain_name, domain_dict in sub_domain_results.items():
            if isinstance(domain_dict, dict):
                for field_name, field_value in domain_dict.items():
                    # We drop the sub_domain name entirely and just use the inner heading
                    flat[field_name] = field_value
                    all_keys.add(field_name)
                    
    except Exception as e:
        pass
        
    flattened_rows.append(flat)

# Sort fieldnames but keep the base_columns at the very beginning
dynamic_keys = sorted(list(all_keys - set(base_columns)))
fieldnames = base_columns + dynamic_keys

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flattened_rows)

print(f"Successfully flattened {len(flattened_rows)} experiments!")
print(f"Saved to: {output_file}")

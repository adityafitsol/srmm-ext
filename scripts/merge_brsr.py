import json
import os

def merge_brsr_data():
    base_path = "/home/g0dx1lla/final-company-json/"
    output_file = os.path.join(base_path, "consolidated-brsr.json")
    
    # List of files to process
    input_files = [
        "brsr-2021-22.json",
        "brsr-2022-23.json",
        "brsr-2023-24.json",
        "brsr-2024-25.json",
        "brsr-2025-26.json",
        "brsr-2026.json",
    ]
    
    consolidated_data = {}

    for file_name in input_files:
        file_path = os.path.join(base_path, file_name)
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_name}. Skipping...")
            continue
            
        with open(file_path, 'r') as f:
            try:
                content = json.load(f)
                records = content.get("data", [])
                
                for record in records:
                    company = record.get("companyName")
                    # Create a year key like "2023-2024"
                    year_key = f"{record.get('fyFrom')}-{record.get('fyTo')}"
                    
                    if company not in consolidated_data:
                        consolidated_data[company] = {}
                    
                    # Store only the required fields
                    consolidated_data[company][year_key] = {
                        "companyName": company,
                        "attachmentFile": record.get("attachmentFile"),
                        "xbrlFile": record.get("xbrlFile"),
                        "fyFrom": record.get("fyFrom"),
                        "fyTo": record.get("fyTo")
                    }
            except json.JSONDecodeError:
                print(f"Error parsing {file_name}. Skipping...")

    # Write the consolidated data to the output file
    with open(output_file, 'w') as out_f:
        json.dump(consolidated_data, out_f, indent=2)
    
    print(f"Successfully merged data into {output_file}")

if __name__ == "__main__":
    merge_brsr_data()
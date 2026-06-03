import json
import os

def merge_extended_brsr_data():
    base_path = "/home/g0dx1lla/final-company-json/"
    output_file = os.path.join(base_path, "consolidated-brsr.json")
    
    # List of year-wise files to process
    input_files = [
        "brsr-2021-22.json",
        "brsr-2022-23.json",
        "brsr-2023-24.json",
        "brsr-2024-25.json",
        "brsr-2025-26.json"
    ]
    
    consolidated_data = {}

    for file_name in input_files:
        file_path = os.path.join(base_path, file_name)
        
        if not os.path.exists(file_path):
            print(f"Skipping {file_name}: File not found.")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                content = json.load(f)
                records = content.get("data", [])
                
                for record in records:
                    company = record.get("companyName")
                    if not company:
                        continue
                        
                    # Create a year key like "2023-2024"
                    year_key = f"{record.get('fyFrom')}-{record.get('fyTo')}"
                    
                    if company not in consolidated_data:
                        consolidated_data[company] = {}
                    
                    # Structure the year-wise data with the requested metrics
                    consolidated_data[company][year_key] = {
                        "companyName": company,
                        "attachmentFile": record.get("attachmentFile"),
                        "xbrlFile": record.get("xbrlFile"),
                        "fyFrom": record.get("fyFrom"),
                        "fyTo": record.get("fyTo"),
                        "cdpRating": {
                            "cdpClimate": record.get("cdpClimate"),
                            "cdpWaterSecurity": record.get("cdpWaterSecurity"),
                            "cdpForest": record.get("cdpForest")
                        },
                        "djsiInclusion": record.get("DJSI Inclusion"),
                        "s&pRating": record.get("S & P Rating"),
                        "srmmScore": record.get("SRMM Score"),
                        "ecoVadis": record.get("ecoVadis"),
                        "maturityLevel": record.get("maturityLevel"),
                        "maturityStage": record.get("maturityStage")
                    }
            except json.JSONDecodeError:
                print(f"Error: Failed to parse {file_name}.")

    # Save the organized structure to the output file
    with open(output_file, 'w', encoding='utf-8') as out_f:
        json.dump(consolidated_data, out_f, indent=2)
    
    print(f"Consolidation complete. Output saved to: {output_file}")

if __name__ == "__main__":
    merge_extended_brsr_data()
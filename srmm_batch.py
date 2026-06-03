import os
import sys
import json
import requests
import pandas as pd
from pypdf import PdfReader
from google import genai
from google.genai import types
from google.oauth2 import service_account
from termcolor import colored
import concurrent.futures
from scripts.utils import get_master_list, sort_df_by_master, extract_text_from_pdf
import time
import argparse

# Configuration
SRMM_FILE = 'SRMM_Questions_Extracted.md'
CREDENTIALS_FILE = 'quiet-mechanic-451307-s9-1bd5db312124.json'
TEMP_DIR = 'temp'
DATA_DIR = 'data'
OUTPUT_DIR = 'output'

def get_gemini_client():
    if not os.path.exists(CREDENTIALS_FILE):
        print(colored(f"Error: Credentials file '{CREDENTIALS_FILE}' not found.", "red"))
        sys.exit(1)
        
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    return genai.Client(vertexai=True, project='quiet-mechanic-451307-s9', location='us-central1', credentials=credentials)

def download_pdf(url, output_path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    response = requests.get(url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def analyze_chunk(client, company_name, pdf_text, srmm_chunk, chunk_index):
    prompt_str = f"""
You are an expert ESG and sustainability analyst. 
Your task is to analyze the following Business Responsibility and Sustainability Report (BRSR) of '{company_name}' and score it according to the provided subset of the SRMM (Sustainability Reporting Maturity Model) framework.

For each Point No. in the provided SRMM framework subset, find the relevant information in the BRSR text and determine the appropriate score based on the Scaling rules. Be precise and objective.

Output your response strictly as a JSON array of objects.
Each object must have the exact following keys:
- "Point No.": The point number from the SRMM framework (e.g., "18", "24", "1.1a").
- "Parameter/Question": The text of the parameter or question.
- "Scaling": The scaling criteria for scoring.
- "ScoreGiven": The integer score you determined based on the BRSR text. If the parameter is not applicable or not reported, give 0.
- "MaxScore": The maximum possible score for this parameter.
- "Reason": A brief explanation (1-2 sentences) citing specific metrics, page numbers, or facts from the text that justify why this specific score was given.

SRMM FRAMEWORK SUBSET (Chunk {chunk_index}):
{srmm_chunk}

BRSR REPORT TEXT:
{pdf_text[:3000000]} 
"""
    
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=prompt_str,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    return json.loads(response.text)

def parallel_analyze(client, company_name, pdf_text, srmm_text):
    parts = srmm_text.split("### PRINCIPLE")
    
    chunk1 = parts[0] + "### PRINCIPLE" + parts[1] + "### PRINCIPLE" + parts[2] + "### PRINCIPLE" + parts[3]
    chunk2 = "### PRINCIPLE" + parts[4] + "### PRINCIPLE" + parts[5] + "### PRINCIPLE" + parts[6]
    chunk3 = "### PRINCIPLE" + parts[7] + "### PRINCIPLE" + parts[8] + "### PRINCIPLE" + parts[9]
    
    chunks = [chunk1, chunk2, chunk3]
    all_scores = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i, chunk in enumerate(chunks, 1):
            futures.append(executor.submit(analyze_chunk, client, company_name, pdf_text, chunk, i))
            
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_scores.extend(result)
            except Exception as exc:
                print(colored(f"\n[-] One chunk failed with exception: {exc}", "red"))
                
    return all_scores

def process_company(client, company_data, year, srmm_text):
    company_name = company_data['companyName']
    pdf_url = company_data['attachmentFile']
    
    if not pdf_url or str(pdf_url).lower() == 'null':
        print(colored(f"[-] Skipping {company_name}: No PDF attachment URL.", "yellow"))
        return False

    output_dir = os.path.join(OUTPUT_DIR, year)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    safe_name = company_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    excel_filename = os.path.join(output_dir, f"{safe_name}_srmm_{year}_brsr_score.xlsx")
    
    if os.path.exists(excel_filename):
        print(colored(f"[+] Skipping {company_name}: Already processed ({excel_filename}).", "green"))
        return True

    print(colored(f"\n[*] Processing: {company_name}", "cyan", attrs=["bold"]))
    pdf_temp_file = os.path.join(TEMP_DIR, f"temp_{safe_name}.pdf")
    
    try:
        print(colored("    Downloading PDF...", "cyan"))
        download_pdf(pdf_url, pdf_temp_file)
        
        print(colored("    Extracting text...", "cyan"))
        pdf_text = extract_text_from_pdf(pdf_temp_file)
        
        print(colored("    Analyzing with AI...", "cyan"))
        scores = parallel_analyze(client, company_name, pdf_text, srmm_text)
        
        if not scores:
            print(colored(f"[-] Failed to get scores for {company_name}", "red"))
            return False
            
        total_score_obtained = 0
        grand_total_max = 300
        
        for score in scores:
            score['Company Name'] = company_name
            try:
                total_score_obtained += int(score.get('ScoreGiven', 0))
            except ValueError:
                pass

        score_percentage = (total_score_obtained / grand_total_max) * 100

        df = pd.DataFrame(scores)
        cols = ['Company Name', 'Point No.', 'Parameter/Question', 'Scaling', 'ScoreGiven', 'MaxScore', 'Reason']
        for col in cols:
            if col not in df.columns:
                df[col] = None
        df = df[cols]
        
        try:
            master_list = get_master_list(SRMM_FILE)
            df = sort_df_by_master(df, master_list)
        except Exception as e:
            pass
        
        summary_data = [
            {'Company Name': company_name, 'Point No.': 'TOTAL', 'Parameter/Question': 'Total Score', 'Scaling': '', 'ScoreGiven': total_score_obtained, 'MaxScore': grand_total_max, 'Reason': ''},
            {'Company Name': company_name, 'Point No.': 'PERCENTAGE', 'Parameter/Question': 'Score Out of 100', 'Scaling': '', 'ScoreGiven': round(score_percentage, 2), 'MaxScore': 100, 'Reason': ''}
        ]
        df = pd.concat([df, pd.DataFrame(summary_data)], ignore_index=True)
        
        df.to_excel(excel_filename, index=False)
        print(colored(f"[+] Successfully processed {company_name} -> {excel_filename}", "green"))
        
    except Exception as e:
        print(colored(f"[-] Error processing {company_name}: {e}", "red"))
        return False
    finally:
        if os.path.exists(pdf_temp_file):
            os.remove(pdf_temp_file)
            
    return True

def main():
    parser = argparse.ArgumentParser(description="SRMM BRSR Batch AI Scoring CLI Tool")
    parser.add_argument("year", help="Year to process (e.g., 2024-25) or 'all' to process all years in data dir.")
    args = parser.parse_args()
    
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    client = get_gemini_client()
    
    with open(SRMM_FILE, 'r', encoding='utf-8') as f:
        srmm_text = f.read()

    years_to_process = []
    if args.year.lower() == 'all':
        for f in os.listdir(DATA_DIR):
            if f.startswith('brsr-') and f.endswith('.json'):
                year_part = f.replace('brsr-', '').replace('.json', '')
                years_to_process.append(year_part)
    else:
        years_to_process.append(args.year)
        
    for year in years_to_process:
        json_filename = os.path.join(DATA_DIR, f"brsr-{year}.json")
        if not os.path.exists(json_filename):
            print(colored(f"[-] Data file {json_filename} not found. Skipping.", "yellow"))
            continue
            
        print(colored(f"\n{'='*50}\nStarting batch processing for year: {year}\n{'='*50}", "cyan", attrs=["bold"]))
        
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            companies = data.get('data', [])
            
        print(colored(f"[*] Found {len(companies)} companies in {year}", "cyan"))
        
        for idx, company in enumerate(companies, 1):
            print(colored(f"\n--- Company {idx}/{len(companies)} ---", "yellow"))
            process_company(client, company, year, srmm_text)
            # Small delay to avoid hitting rate limits
            time.sleep(2)

if __name__ == "__main__":
    main()
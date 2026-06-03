import os
import json
import time
import requests
import pandas as pd
from pypdf import PdfReader
from google import genai
from google.genai import types
from google.oauth2 import service_account

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import get_master_list, sort_df_by_master, extract_text_from_pdf

# File paths
JSON_FILE = 'data/brsr-2021-22.json'
EXCEL_FILE = 'output/BRSR_Scores_2021_22.xlsx'
SRMM_FILE = 'SRMM_Questions_Extracted.md'
CREDENTIALS_FILE = 'quiet-mechanic-451307-s9-1bd5db312124.json'
PDF_TEMP_FILE = 'temp_brsr.pdf'

def get_gemini_client():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    return genai.Client(vertexai=True, project='quiet-mechanic-451307-s9', location='us-central1', credentials=credentials)

def download_pdf(url, output_path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def process_company(client, company_data, srmm_text):
    company_name = company_data['companyName']
    pdf_url = company_data['attachmentFile']
    
    print(f"Downloading PDF for {company_name} from {pdf_url}...")
    try:
        download_pdf(pdf_url, PDF_TEMP_FILE)
    except Exception as e:
        print(f"Failed to download PDF for {company_name}: {e}")
        return None
    
    print(f"Extracting text from PDF...")
    try:
        pdf_text = extract_text_from_pdf(PDF_TEMP_FILE)
    except Exception as e:
        print(f"Failed to extract text from PDF: {e}")
        return None
        
    print(f"Analyzing with Gemini 2.5 Pro (Text length: {len(pdf_text)} chars)...")
    
    prompt = f"""
You are an expert ESG and sustainability analyst. 
Your task is to analyze the following Business Responsibility and Sustainability Report (BRSR) of '{company_name}' and score it according to the provided SRMM (Sustainability Reporting Maturity Model) framework.

For each Point No. in the SRMM framework, find the relevant information in the BRSR text and determine the appropriate score based on the Scaling rules. Be precise and objective.

Output your response strictly as a JSON array of objects.
Each object must have the exact following keys:
- "Point No.": The point number from the SRMM framework (e.g., "18", "24", "1.1a").
- "Parameter/Question": The text of the parameter or question.
- "Scaling": The scaling criteria for scoring.
- "ScoreGiven": The integer score you determined based on the BRSR text. If not reported, give 0 as per rules.
- "MaxScore": The maximum possible score for this parameter.

SRMM FRAMEWORK:
{srmm_text}

BRSR REPORT TEXT:
{pdf_text[:3000000]} 
"""
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        scores = json.loads(response.text)
        
        # Add company name to each record
        for score in scores:
            score['Company Name'] = company_name
            
        return scores
    except Exception as e:
        print(f"Gemini API error for {company_name}: {e}")
        return None

def main():
    # Load SRMM criteria
    with open(SRMM_FILE, 'r', encoding='utf-8') as f:
        srmm_text = f.read()

    # Load Company list
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        companies = json.load(f)['data']

    # Load existing progress (Checkpoint)
    processed_companies = set()
    if os.path.exists(EXCEL_FILE):
        df_existing = pd.read_excel(EXCEL_FILE)
        if 'Company Name' in df_existing.columns:
            processed_companies = set(df_existing['Company Name'].unique())
            print(f"Found existing Excel file. {len(processed_companies)} companies already processed.")

    client = get_gemini_client()
    
    processed_count = 0
    for company in companies:
        company_name = company['companyName']
        if company_name in processed_companies:
            print(f"Skipping {company_name} - already processed.")
            continue
            
        print(f"\n--- Processing {company_name} ---")
        scores = process_company(client, company, srmm_text)
        
        if scores:
            df_new = pd.DataFrame(scores)
            
            # Rearrange columns
            cols = ['Company Name', 'Point No.', 'Parameter/Question', 'Scaling', 'ScoreGiven', 'MaxScore']
            for col in cols:
                if col not in df_new.columns:
                    df_new[col] = None
            df_new = df_new[cols]
            
            # Sort the new dataframe according to the master list
            try:
                master_list = get_master_list(SRMM_FILE)
                df_new = sort_df_by_master(df_new, master_list)
            except Exception as e:
                print(f"Warning: Failed to sort DataFrame: {e}")
            
            # Append to Excel immediately (Checkpointing)
            if os.path.exists(EXCEL_FILE):
                df_existing = pd.read_excel(EXCEL_FILE)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined.to_excel(EXCEL_FILE, index=False)
            else:
                df_new.to_excel(EXCEL_FILE, index=False)
                
            print(f"Successfully processed and saved {company_name}.")
            processed_companies.add(company_name)
            processed_count += 1
        else:
            print(f"Failed to process {company_name}.")
            
            # Stop if failed to avoid looping errors blindly
            # break

if __name__ == '__main__':
    main()

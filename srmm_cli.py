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
from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter, WordCompleter
from prompt_toolkit.styles import Style
import threading
import time
import concurrent.futures
from scripts.utils import get_master_list, sort_df_by_master, extract_text_from_pdf

# Configuration
SRMM_FILE = 'SRMM_Questions_Extracted.md'
CREDENTIALS_FILE = 'quiet-mechanic-451307-s9-1bd5db312124.json'
TEMP_DIR = 'temp'
DATA_DIR = 'data'
OUTPUT_DIR = 'output'
PDF_TEMP_FILE = os.path.join(TEMP_DIR, 'temp_brsr_cli.pdf')

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
    response = requests.get(url, headers=headers, stream=True, timeout=30)
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
    # Split the SRMM text into roughly 3 logical chunks based on "### PRINCIPLE" to ensure context stays intact
    parts = srmm_text.split("### PRINCIPLE")
    
    # Re-attach the split keyword and group them
    # parts[0] contains Section A & B
    chunk1 = parts[0] + "### PRINCIPLE" + parts[1] + "### PRINCIPLE" + parts[2] + "### PRINCIPLE" + parts[3] # A, B, P1, P2, P3
    chunk2 = "### PRINCIPLE" + parts[4] + "### PRINCIPLE" + parts[5] + "### PRINCIPLE" + parts[6] # P4, P5, P6
    chunk3 = "### PRINCIPLE" + parts[7] + "### PRINCIPLE" + parts[8] + "### PRINCIPLE" + parts[9] # P7, P8, P9
    
    chunks = [chunk1, chunk2, chunk3]
    all_scores = []
    
    # Run requests in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i, chunk in enumerate(chunks, 1):
            futures.append(executor.submit(analyze_chunk, client, company_name, pdf_text, chunk, i))
            
        try:
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    all_scores.extend(result)
                except Exception as exc:
                    print(colored(f"\n[-] One chunk failed with exception: {exc}", "red"))
        except KeyboardInterrupt:
            print(colored("\n\n[!] User interrupted! Cancelling pending tasks and saving partial results...", "yellow"))
            for f in futures:
                f.cancel()
                
    return all_scores

def main():
    print(colored("="*50, "cyan", attrs=["bold"]))
    print(colored("   SRMM BRSR AI Scoring CLI Tool", "cyan", attrs=["bold"]))
    print(colored("="*50, "cyan", attrs=["bold"]))
    
    style = Style.from_dict({
        'prompt': 'ansicyan bold',
    })
    
    # 1. Get Year Input with autocomplete
    years = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026"]
    year_completer = WordCompleter(years)
    
    try:
        year_input = prompt("Enter the target year (Press TAB to see options): ", completer=year_completer, style=style).strip()
    except KeyboardInterrupt:
        sys.exit(0)
    
    json_filename = os.path.join(DATA_DIR, f"brsr-{year_input}.json")
    if not os.path.exists(json_filename):
        print(colored(f"Error: Dataset file '{json_filename}' does not exist.", "red"))
        sys.exit(1)
        
    # Read the dataset to get companies
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            companies = data.get('data', [])
    except Exception as e:
        print(colored(f"Error reading {json_filename}: {e}", "red"))
        sys.exit(1)
        
    # 2. Real-time Searchable Company Input
    company_names = [c['companyName'] for c in companies]
    company_completer = FuzzyWordCompleter(company_names)
    
    print(colored("\n[*] Start typing the company name (e.g., 'ad').", "yellow"))
    print(colored("[*] A dropdown menu will appear dynamically! Use UP/DOWN arrows and hit ENTER.", "yellow"))
    
    try:
        company_input = prompt("Enter Company Name: ", completer=company_completer, style=style).strip()
    except KeyboardInterrupt:
        sys.exit(0)
    
    company_data = None
    for c in companies:
        if c['companyName'].lower() == company_input.lower():
            company_data = c
            break
            
    if not company_data:
        print(colored(f"Could not find exact match for '{company_input}'. Please make sure to select from the dropdown.", "red"))
        sys.exit(1)
        
    company_name = company_data['companyName']
    pdf_url = company_data['attachmentFile']
    
    print(colored(f"\n[+] Selected: {company_name}", "green", attrs=["bold"]))
    print(colored(f"    URL: {pdf_url}", "cyan"))
    
    if not pdf_url or str(pdf_url).lower() == 'null':
        print(colored("Error: No PDF attachment URL found for this company in the dataset.", "red"))
        sys.exit(1)

    # 3. Download & Extract
    print(colored("\n[*] Downloading PDF report...", "cyan"))
    try:
        download_pdf(pdf_url, PDF_TEMP_FILE)
    except KeyboardInterrupt:
        print(colored("\n[!] Download interrupted.", "red"))
        sys.exit(1)
    except Exception as e:
        print(colored(f"[-] Failed to download PDF: {e}", "red"))
        sys.exit(1)
        
    print(colored("[*] Extracting text from PDF...", "cyan"))
    try:
        pdf_text = extract_text_from_pdf(PDF_TEMP_FILE)
    except KeyboardInterrupt:
        print(colored("\n[!] Extraction interrupted.", "red"))
        sys.exit(1)
    except Exception as e:
        print(colored(f"[-] Failed to extract text: {e}", "red"))
        sys.exit(1)
        
    print(colored(f"[+] Text extracted successfully. Length: {len(pdf_text)} characters.", "green"))

    # 4. Analyze with Gemini
    with open(SRMM_FILE, 'r', encoding='utf-8') as f:
        srmm_text = f.read()
        
    print(colored("\n[*] Initiating AI Analysis with Gemini 2.5 Pro...", "cyan", attrs=["bold"]))
    print(colored("    (Please be patient! Evaluating a 70k+ char document against 90+ SRMM criteria takes ~60-120 seconds)", "yellow"))
    
    client = get_gemini_client()
    
    def spinner_task(event):
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        start_time = time.time()
        while not event.is_set():
            elapsed = int(time.time() - start_time)
            sys.stdout.write(f"\r  {colored(spinner[i], 'cyan')} {colored(f'Processing... ({elapsed}s elapsed)', 'cyan')}")
            sys.stdout.flush()
            i = (i + 1) % len(spinner)
            time.sleep(0.1)
        sys.stdout.write('\r' + ' ' * 50 + '\r') # clear line
        sys.stdout.flush()

    stop_spinner = threading.Event()
    spinner_thread = threading.Thread(target=spinner_task, args=(stop_spinner,))
    spinner_thread.start()
    
    scores = []
    try:
        scores = parallel_analyze(client, company_name, pdf_text, srmm_text)
    except KeyboardInterrupt:
        pass # Already handled inside parallel_analyze, it returns partial list
    except Exception as e:
        stop_spinner.set()
        spinner_thread.join()
        print(colored(f"\n[-] Gemini API Error: {e}", "red"))
        sys.exit(1)
        
    stop_spinner.set()
    spinner_thread.join()
    
    if not scores:
        print(colored("\n[-] No data was successfully processed. Exiting without saving.", "red"))
        if os.path.exists(PDF_TEMP_FILE):
            os.remove(PDF_TEMP_FILE)
        sys.exit(0)
        
    # 5. Process Scores & Create Output
    print(colored("\n[*] Analysis complete. Compiling results...", "cyan"))
    
    total_score_obtained = 0
    grand_total_max = 300 # According to SRMM rules
    
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
    
    # Sort the dataframe according to the master list
    try:
        master_list = get_master_list(SRMM_FILE)
        df = sort_df_by_master(df, master_list)
    except Exception as e:
        print(colored(f"[-] Warning: Failed to sort DataFrame: {e}", "yellow"))
    
    # Append summary rows
    summary_data = [
        {'Company Name': company_name, 'Point No.': 'TOTAL', 'Parameter/Question': 'Total Score', 'Scaling': '', 'ScoreGiven': total_score_obtained, 'MaxScore': grand_total_max, 'Reason': ''},
        {'Company Name': company_name, 'Point No.': 'PERCENTAGE', 'Parameter/Question': 'Score Out of 100', 'Scaling': '', 'ScoreGiven': round(score_percentage, 2), 'MaxScore': 100, 'Reason': ''}
    ]
    df = pd.concat([df, pd.DataFrame(summary_data)], ignore_index=True)
    
    # 6. Save File
    output_dir = os.path.join(OUTPUT_DIR, year_input)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    safe_name = company_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    excel_filename = os.path.join(output_dir, f"{safe_name}_srmm_{year_input}_brsr_score.xlsx")
    
    df.to_excel(excel_filename, index=False)
    
    # Cleanup Temp File
    if os.path.exists(PDF_TEMP_FILE):
        os.remove(PDF_TEMP_FILE)
        
    print(colored("="*50, "green", attrs=["bold"]))
    print(colored(f"   Analysis Report for: {company_name}", "yellow", attrs=["bold"]))
    print(colored("="*50, "green", attrs=["bold"]))
    print(colored(f"Total Score Obtained: {total_score_obtained} / {grand_total_max}", "white", attrs=["bold"]))
    print(colored(f"Maturity Percentage:  {score_percentage:.2f}%", "white", attrs=["bold"]))
    
    if score_percentage <= 25:
        level = "Level 1: Formative Stage"
    elif score_percentage <= 50:
        level = "Level 2: Emerging Stage"
    elif score_percentage <= 75:
        level = "Level 3: Established Stage"
    else:
        level = "Level 4: Leading by Example"
        
    print(colored(f"Maturity Level:       {level}", "white", attrs=["bold"]))
    print(colored("="*50, "green", attrs=["bold"]))
    print(colored(f"\n[+] Success! Data saved to: {excel_filename}\n", "green"))

if __name__ == "__main__":
    main()

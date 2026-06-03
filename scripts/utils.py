import os
import re
import pandas as pd

def normalize_text(text, is_point_no=False):
    if not isinstance(text, str):
        return ""
    if is_point_no:
        # For point numbers, just lowercase and remove common separators
        text = text.lower().replace(' ', '').replace('-', '').replace('–', '')
        text = re.sub(r'[^a-z0-9\(\)\.]', '', text)
        return text
    
    # For questions, be more thorough
    # Replace slashes, dashes, etc. with space to separate words
    text = text.replace('/', ' ').replace('-', ' ').replace('–', ' ').replace('—', ' ')
    text = text.lower()
    # Remove all non-alphanumeric except space
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_master_list(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    master_list = []
    in_table = False
    for line in lines:
        if '| Point No.' in line:
            in_table = True
            continue
        if in_table:
            if line.startswith('|---'): continue
            if not line.startswith('|'):
                in_table = False
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                point_no = parts[1]
                question = parts[2]
                if point_no and question:
                    master_list.append({
                        'point_no': point_no,
                        'question': question,
                        'norm_point': normalize_text(point_no, is_point_no=True),
                        'norm_quest': normalize_text(question)
                    })
    return master_list

def sort_df_by_master(df, master_list):
    if df.empty:
        return df
        
    ordered_rows = []
    used_indices = set()
    
    df_norm = df.copy()
    df_norm['norm_point'] = df_norm['Point No.'].apply(lambda x: normalize_text(x, is_point_no=True))
    df_norm['norm_quest'] = df_norm['Parameter/Question'].apply(normalize_text)
    
    for master_item in master_list:
        match = df_norm[
            (df_norm['norm_point'] == master_item['norm_point']) & 
            (df_norm['norm_quest'] == master_item['norm_quest'])
        ]
        
        if not match.empty:
            for idx in match.index:
                if idx not in used_indices:
                    ordered_rows.append(df.iloc[idx])
                    used_indices.add(idx)
        else:
            match_fallback = df_norm[
                (df_norm['norm_point'] == master_item['norm_point']) & 
                (df_norm['norm_quest'].apply(lambda x: x.startswith(master_item['norm_quest']) or master_item['norm_quest'].startswith(x)))
            ]
            if not match_fallback.empty:
                for idx in match_fallback.index:
                    if idx not in used_indices:
                        ordered_rows.append(df.iloc[idx])
                        used_indices.add(idx)

    for idx in range(len(df)):
        if idx not in used_indices:
            ordered_rows.append(df.iloc[idx])

    if not ordered_rows:
        return df

    sorted_df = pd.DataFrame(ordered_rows)
    return sorted_df

def extract_text_from_pdf(pdf_path):
    from pypdf import PdfReader
    try:
        from pdf2image import convert_from_path
        import pytesseract
        ocr_available = True
    except ImportError:
        ocr_available = False

    reader = PdfReader(pdf_path)
    text = ""
    for i, page in enumerate(reader.pages):
        extracted = page.extract_text()
        # If the page yields very little text, it's likely a scanned image.
        if extracted and len(extracted.strip()) > 50:
            text += extracted + "\n"
        elif ocr_available:
            try:
                print(f"  [OCR] Scanning page {i+1} (image-based or low text)...")
                # first_page and last_page are 1-indexed in pdf2image
                images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1)
                if images:
                    ocr_text = pytesseract.image_to_string(images[0])
                    text += ocr_text + "\n"
            except Exception as e:
                print(f"  [OCR] Failed on page {i+1}: {e}")
                if extracted:
                    text += extracted + "\n"
        else:
            if extracted:
                text += extracted + "\n"
    return text

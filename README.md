# SRMM BRSR AI Scoring Tool

This is an interactive Command Line Interface (CLI) application powered by Gemini 2.5 Pro that automates the extraction and scoring of Business Responsibility and Sustainability Reports (BRSR) based on the SRMM framework.

## Project Structure

- `srmm_cli.py` - The main interactive CLI application.
- `data/` - Contains the `brsr-*.json` datasets listing companies and their PDF links.
- `output/` - Contains the generated Excel scorecards, neatly organized by year (e.g., `output/2024-25/`).
- `temp/` - Used temporarily during PDF downloads to keep the workspace clean.
- `scripts/` - Older or alternative processing scripts (like batch processing logic).
- `SRMM_Questions_Extracted.md` - The reference criteria used by the AI to score the reports.
- `quiet-mechanic-*.json` - The service account credentials for Gemini API.

## Installation for Beginners

1. Ensure you have `python3` installed on your system.
2. Open your terminal in this directory.
3. Run the setup script to automatically create a virtual environment and install dependencies:
   ```bash
   chmod +x setup.sh run.sh
   ./setup.sh
   ```

## How to Run

Simply run the startup script:

```bash
./run.sh
```

**Using the Interactive UI:**
1. **Year Selection:** Type the year (e.g., `2024-25`) or hit `TAB` to see autocomplete options.
2. **Company Search:** Start typing the name of a company (e.g., `ad`). A dropdown menu will appear. Use the `UP` and `DOWN` arrow keys to select the exact company you want, then press `ENTER`.
3. **Execution:** The script will automatically fetch the PDF, read it, invoke Gemini 2.5 Pro for analysis, and calculate your final scores & maturity levels.
4. **Results:** Your generated Excel file will be neatly saved inside the `output/` folder!

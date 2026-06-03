#!/bin/bash
set -e

echo -e "\033[1;36m==================================================\033[0m"
echo -e "\033[1;36m      SRMM BRSR AI Scoring - Setup Script         \033[0m"
echo -e "\033[1;36m==================================================\033[0m"

echo -e "\n\033[1;33m[*] Creating directories...\033[0m"
mkdir -p data output temp scripts

if [ ! -d "venv" ]; then
    echo -e "\033[1;33m[*] Creating Python virtual environment (venv)...\033[0m"
    python3 -m venv venv
else
    echo -e "\033[1;32m[+] Virtual environment already exists.\033[0m"
fi

echo -e "\033[1;33m[*] Activating virtual environment and installing dependencies...\033[0m"
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo -e "\n\033[1;32m==================================================\033[0m"
echo -e "\033[1;32m[+] Setup Complete! \033[0m"
echo -e "\033[1;32m[+] You can now run the application by typing:\033[0m"
echo -e "\033[1;36m    ./run.sh\033[0m"
echo -e "\033[1;32m==================================================\033[0m"

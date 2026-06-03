#!/bin/bash
set -e

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

source venv/bin/activate
python3 srmm_cli.py

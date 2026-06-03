#!/bin/bash
set -e

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: ./run_batch.sh <year|all>"
    echo "Example: ./run_batch.sh 2024-25"
    exit 1
fi

source venv/bin/activate
python3 srmm_batch.py "$1"

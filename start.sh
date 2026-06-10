#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Starting application..."
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port $PORT

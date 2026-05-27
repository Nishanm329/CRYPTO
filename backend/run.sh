#!/bin/bash
cd /Users/nishanmaharaj/Music/crypto-signals/backend
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

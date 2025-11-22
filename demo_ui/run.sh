#!/bin/bash

# Quick start script for the voting demo UI

echo "Starting Voting Demo UI..."

# Check if .env exists, if not create from example
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file to configure your API URL"
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Set Flask app
export FLASK_APP=app.py

# Run the application
echo ""
echo "=========================================="
echo "Voting Demo UI is starting..."
echo "Access the application at: http://localhost:3000"
echo "Press CTRL+C to stop"
echo "=========================================="
echo ""

python app.py

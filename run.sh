#!/bin/bash
# Simple run script for Safe Parking Florence Bot

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Check if config exists
if [ ! -f "config/config.yaml" ]; then
    echo "❌ Configuration file not found"
    echo "Please copy config/config.example.yaml to config/config.yaml and configure it"
    exit 1
fi

# Run the bot
echo "🚗 Starting Safe Parking Florence Bot..."
python main.py

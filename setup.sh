#!/bin/bash
# Setup script for Safe Parking Florence Bot

set -e

echo "🚗 Safe Parking Florence - Setup Script"
echo "========================================"
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Found Python $PYTHON_VERSION"

# Check if major.minor version is at least 3.8
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 8 ]); then
    echo "❌ Python version must be 3.8 or higher"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo "✅ Virtual environment recreated"
    fi
else
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Dependencies installed"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p data state config

# Setup configuration
echo ""
if [ ! -f "config/config.yaml" ]; then
    echo "Creating configuration file..."
    cp config/config.example.yaml config/config.yaml
    echo "✅ Configuration file created: config/config.yaml"
    echo ""
    echo "⚠️  IMPORTANT: You need to edit config/config.yaml with your:"
    echo "   - Telegram bot token (from @BotFather)"
    echo "   - Telegram user ID (from @userinfobot)"
    echo ""
    echo "Run: nano config/config.yaml"
else
    echo "✅ Configuration file already exists"
fi

echo ""
echo "========================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/config.yaml with your bot token and user ID"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Run the bot: python main.py"
echo ""
echo "For deployment to Google Cloud, see README.md"
echo "========================================"

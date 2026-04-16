# Quick Start Script for Bubble Scanner
# Double-click this file in Finder to run (if Terminal access is available)

#!/bin/bash

echo "🧪 Bubble Scanner Quick Start"
echo "=============================="

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📁 Project directory: $SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚙️  Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
echo "📦 Installing/updating packages..."
pip install -r requirements.txt

# Check if packages are installed correctly
echo "✅ Verifying installation..."
python3 -c "import flask, cv2, numpy, fitz; print('✅ All packages ready!')" || {
    echo "❌ Package installation failed. Please run manually:"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
}

echo ""
echo "🚀 Starting Bubble Scanner..."
echo "📱 The web interface will open at: http://localhost:5001"
echo "🛑 Press Ctrl+C to stop the scanner"
echo ""

# Start Flask
python3 app.py
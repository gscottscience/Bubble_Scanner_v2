#!/bin/bash
# Bubble Scanner Launcher Script
# This script handles virtual environment activation and starts the Flask app

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo -e "${BLUE}Bubble Scanner Launcher${NC}"
echo -e "Project directory: ${SCRIPT_DIR}"

# Change to the project directory
cd "$SCRIPT_DIR"

# Function to check if Python package is installed
check_package() {
    $1 -c "import $2" 2>/dev/null
    return $?
}

# Try to find and activate virtual environment
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source "$SCRIPT_DIR/venv/bin/activate"
    PYTHON_CMD="python"
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
elif [ -d "$SCRIPT_DIR/.venv" ]; then
    echo -e "${YELLOW}Activating virtual environment (.venv)...${NC}"
    source "$SCRIPT_DIR/.venv/bin/activate"
    PYTHON_CMD="python"
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo -e "${YELLOW}Using system Python 3${NC}"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    echo -e "${YELLOW}Using system Python${NC}"
else
    echo -e "${RED}❌ Error: Python not found. Please install Python 3.${NC}"
    echo "Visit https://www.python.org/downloads/ to download Python"
    read -p "Press any key to exit..."
    exit 1
fi

# Check if required packages are installed
echo -e "${YELLOW}Checking required packages...${NC}"
MISSING_PACKAGES=()

if ! check_package "$PYTHON_CMD" "flask"; then
    MISSING_PACKAGES+=("flask")
fi

if ! check_package "$PYTHON_CMD" "cv2"; then
    MISSING_PACKAGES+=("opencv-python")
fi

if ! check_package "$PYTHON_CMD" "numpy"; then
    MISSING_PACKAGES+=("numpy")
fi

if ! check_package "$PYTHON_CMD" "fitz"; then
    MISSING_PACKAGES+=("PyMuPDF")
fi

# Install missing packages if any
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}Installing missing packages: ${MISSING_PACKAGES[*]}${NC}"
    $PYTHON_CMD -m pip install "${MISSING_PACKAGES[@]}"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Packages installed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to install packages. Please run manually:${NC}"
        echo "  $PYTHON_CMD -m pip install ${MISSING_PACKAGES[*]}"
        read -p "Press any key to exit..."
        exit 1
    fi
fi

# Check for app.py
if [ ! -f "$SCRIPT_DIR/app.py" ]; then
    echo -e "${RED}❌ Error: app.py not found in $SCRIPT_DIR${NC}"
    read -p "Press any key to exit..."
    exit 1
fi

echo -e "${GREEN}✓ All requirements satisfied${NC}"
echo -e "${BLUE}Starting Bubble Scanner...${NC}"

# Start the Flask app in the background
$PYTHON_CMD app.py &
FLASK_PID=$!

# Wait a moment for the server to start
echo "Waiting for server to start..."
sleep 5

# Check if the server is running
if kill -0 $FLASK_PID 2>/dev/null; then
    echo -e "${GREEN}✅ Bubble Scanner is running!${NC}"
    echo -e "${GREEN}🌐 Web interface: http://localhost:5001${NC}"
    echo -e "${BLUE}📁 Project folder: $SCRIPT_DIR${NC}"
    
    # Open the browser
    echo "Opening browser..."
    open http://localhost:5001
    
    # Show macOS notification
    osascript -e 'display notification "Access the app at http://localhost:5001" with title "Bubble Scanner Started" sound name "Glass"' 2>/dev/null
    
    echo ""
    echo -e "${YELLOW}Instructions:${NC}"
    echo "• The web interface should open automatically in your browser"
    echo "• If it doesn't open, go to: http://localhost:5001"
    echo "• Press Ctrl+C in this terminal to stop the scanner"
    echo "• Or simply close this terminal window"
    echo ""
    
    # Wait for the Flask process or until user interrupts
    trap "echo -e '\n${YELLOW}Shutting down Bubble Scanner...${NC}'; kill $FLASK_PID 2>/dev/null; exit 0" INT
    wait $FLASK_PID
else
    echo -e "${RED}❌ Failed to start Bubble Scanner${NC}"
    echo "Please check the error messages above"
    read -p "Press any key to exit..."
    exit 1
fi
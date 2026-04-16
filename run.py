#!/usr/bin/env python3
"""
Bubble Sheet Scanner - Startup Script
This script checks dependencies and starts the Flask application.
"""

import sys
import subprocess
import os
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed."""
    required_packages = {
        'flask': 'Flask',
        'cv2': 'opencv-python', 
        'numpy': 'numpy',
        'fitz': 'PyMuPDF'
    }
    
    missing_packages = []
    
    for module, package in required_packages.items():
        try:
            __import__(module)
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is NOT installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Please install them with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def create_directories():
    """Create required directories if they don't exist."""
    dirs = [
        'uploads',
        'static',
        'static/debug', 
        'static/preview',
        'templates',
        'test_configs'
    ]
    
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory '{directory}' ready")

def main():
    print("Bubble Sheet Scanner - Starting Up...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        sys.exit(1)
    
    # Create directories
    print("\nCreating required directories...")
    create_directories()
    
    # Start the Flask app
    print("\nStarting Flask application...")
    print("Access the application at: http://localhost:5001")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except ImportError:
        print("Error: Could not import the Flask app. Make sure app.py is in the same directory.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
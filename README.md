# Bubble Scanner - Installation & Setup Guide

A Flask-based web application for scanning and grading bubble sheets from PDFs or images.

## 📋 **Requirements**

- **macOS** (tested on macOS 10.12+)
- **Python 3.7+** 
- **VS Code** (recommended) or Terminal access

## 🚀 **Installation Steps**

### 1. **Download the Project**
- Download/copy the entire `bubble_scanner_v2_web` folder to your Mac
- Place it somewhere accessible (like Desktop or Documents)

### 2. **Install Python Dependencies**
Open Terminal or VS Code terminal and navigate to the project folder:

```bash
cd /path/to/bubble_scanner_v2_web
```

Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install required packages:
```bash
pip install -r requirements.txt
```

### 3. **Verify Installation**
Check that all packages are installed:
```bash
python3 -c "import flask, cv2, numpy, fitz; print('✅ All packages installed successfully!')"
```

## 🎯 **How to Run**

### **Method 1: VS Code (Recommended)**
1. Open **VS Code**
2. Open the `bubble_scanner_v2_web` folder
3. Open **Terminal** in VS Code (`Terminal → New Terminal`)
4. Run these commands:
   ```bash
   source venv/bin/activate
   python3 app.py
   ```
5. Open your browser and go to: **http://localhost:5001**

### **Method 2: Terminal**
1. Open **Terminal**
2. Navigate to project folder:
   ```bash
   cd /path/to/bubble_scanner_v2_web
   ```
3. Activate virtual environment and run:
   ```bash
   source venv/bin/activate
   python3 app.py
   ```
4. Open your browser and go to: **http://localhost:5001**

## 🛑 **How to Stop**
- Press `Ctrl+C` in the terminal where Flask is running

## 📁 **Project Structure**
```
bubble_scanner_v2_web/
├── app.py              # Main Flask application
├── scanner.py          # Core scanning logic
├── requirements.txt    # Python dependencies
├── venv/              # Virtual environment (auto-created)
├── templates/         # HTML templates
├── static/           # CSS and static files
├── test_configs/     # Sample answer key configurations
└── uploads/          # Uploaded files (auto-created)
```

## 🔧 **Troubleshooting**

### **Common Issues:**

1. **"Python not found"**
   - Install Python 3 from: https://www.python.org/downloads/

2. **"Module not found" errors**
   - Make sure virtual environment is activated: `source venv/bin/activate`
   - Reinstall packages: `pip install -r requirements.txt`

3. **"Port already in use"**
   - Stop any existing Flask processes: `pkill -f "python.*app.py"`
   - Or restart your Mac

4. **Browser shows "This site can't be reached"**
   - Make sure Flask is running (you should see output in terminal)
   - Check the correct URL: http://localhost:5001

## 📞 **Support**
If you encounter issues, check that:
- ✅ Python 3 is installed
- ✅ Virtual environment is activated 
- ✅ All packages installed successfully
- ✅ Flask is running without errors
- ✅ Browser is pointing to http://localhost:5001

## 🎓 **Usage**
1. **Select or create an answer key** using the configuration interface
2. **Upload bubble sheet PDFs or images**
3. **Review and download results**

---
*Last updated: October 2025*
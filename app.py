print("=== DEBUG: THIS IS THE REAL APP.PY ===")
print("=== Flask app starting ===")
# --- Multiprocessing worker for PDF page scanning ---
def process_page_proc(args):
    page_num, img_data, config, static_path, parsed_answer_key, answer_key_str, test_name = args
    import numpy as np
    import cv2
    from scanner import BubbleSheetScanner
    import time
    import os
    start = time.time()
    # timing_log = '/tmp/timing_log.txt'
    # def log_timing(msg):
    #     with open(timing_log, 'a') as f:
    #         f.write(msg + '\n')
    # log_timing(f"[TIMING] Start processing page {page_num+1}")
    try:
        nparr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is not None:
            scanner = BubbleSheetScanner(config)
            result = scanner.process_image_data(image, static_path, page_num + 1, {})
            # log_timing(f"[TIMING] Finished processing page {page_num+1} in {time.time()-start:.2f} seconds")
            return (page_num, {
                'page': page_num + 1,
                'studentId': result.get('student_id'),
                'student_id': result.get('student_id'),
                'answers': result.get('answers', []),
                'debug_image_url': result.get('debug_image_url'),
                'error': result.get('error'),
                'answerKey': parsed_answer_key,
                'answer_key': answer_key_str,
                'testName': test_name,
                'tiebreaker_questions': config.get('tiebreaker_questions', [])
            })
        else:
            # log_timing(f"[TIMING] Failed to decode image for page {page_num+1} in {time.time()-start:.2f} seconds")
            return (page_num, {
                'page': page_num + 1,
                'error': 'Could not decode image for page',
                'answerKey': parsed_answer_key,
                'answer_key': answer_key_str,
                'testName': test_name,
                'tiebreaker_questions': config.get('tiebreaker_questions', [])
            })
    except Exception as e:
    # log_timing(f"[TIMING] Exception processing page {page_num+1} after {time.time()-start:.2f} seconds: {e}")
        return (page_num, {
            'page': page_num + 1,
            'error': f'Exception: {e}',
            'answerKey': parsed_answer_key,
            'answer_key': answer_key_str,
            'testName': test_name,
            'tiebreaker_questions': config.get('tiebreaker_questions', [])
        })

# --- Imports and App Initialization ---
import os
import json
import logging
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for

# --- Database Integration ---
from models import ScanResult, SessionLocal, init_db

# Initialize the database (creates tables if not present)
init_db()
from werkzeug.utils import secure_filename
import tempfile
import sys
import numpy as np
import glob

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    print("Warning: PyMuPDF not installed. PDF processing will not work.")
    print("Install with: pip install PyMuPDF")
    PDF_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    print("Warning: OpenCV not installed. Image processing will not work.")
    print("Install with: pip install opencv-python")
    CV2_AVAILABLE = False

from scanner import BubbleSheetScanner, parse_answer_key
from detect_bubbles_and_id import detect_bubbles_and_id

app = Flask(__name__)

# Helper function to get grade-specific answer key name
def get_answer_key_name(base_test_name, student_id):
    """
    Maps base test name + student ID to the correct answer key name.
    Student ID format: First digit is grade level (e.g., 8110 = 8th grade)
    Returns the full answer key name with grade suffix.
    """
    if not student_id or len(str(student_id)) < 1:
        # If no student ID, default to 7th & 8th for most tests
        grade = '7'
    else:
        grade = str(student_id)[0]
    
    # Map grade to answer key suffix
    if grade == '6':
        grade_suffix = ' - 6th Grade'
    else:  # 7 or 8
        grade_suffix = ' - 7th & 8th Grades'
    
    # Special cases for tests that use "Grades 6-8" naming
    if base_test_name == 'Science':
        return 'Science - Grades 6-8'
    
    # Build full answer key name
    return base_test_name + grade_suffix

# --- School List Management ---
SCHOOL_LIST_PATH = Path('school_list.json')

def load_school_list():
    print("DEBUG: load_school_list called")
    if SCHOOL_LIST_PATH.exists():
        with open(SCHOOL_LIST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_school_list(school_dict):
    print("DEBUG: save_school_list called")
    with open(SCHOOL_LIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(school_dict, f, indent=2)

@app.route('/school_list', methods=['GET'])
def school_list_page():
    school_list = load_school_list()
    return render_template('school_list.html', school_list=school_list)

@app.route('/school_list/upload', methods=['POST'])
def upload_school_list():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    try:
        school_dict = json.load(file)
        save_school_list(school_dict)
        return 'School list uploaded successfully', 200
    except Exception as e:
        return f'Error: {e}', 400

print('DEBUG: About to register /api/school_list route')
@app.route('/api/school_list', methods=['GET', 'POST'])
def api_school_list():
    print('DEBUG: Registered /api/school_list route')
    if request.method == 'GET':
        session_name = request.args.get('session', '')
        all_schools = load_school_list()
        # Return schools for the specific session, or empty if not found
        return jsonify(all_schools.get(session_name, {}))
    else:
        try:
            data = request.json
            session_name = data.get('session', '')
            school_dict = data.get('schools', {})
            
            if not session_name:
                return jsonify({'status': 'error', 'error': 'Session name is required'}), 400
            
            # Load existing school lists
            all_schools = load_school_list()
            # Update the specific session's schools
            all_schools[session_name] = school_dict
            save_school_list(all_schools)
            
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 400

# --- Flask app configuration ---
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
print('DEBUG: MAX_CONTENT_LENGTH is set to', app.config['MAX_CONTENT_LENGTH'])

# --- Add all routes after app is defined ---

@app.route('/configure')
def configure_form():
    return render_template('configure.html')

@app.route('/keys')
def keys_page():
    return render_template('keys.html')

@app.route('/scan')
def scan_page():
    return render_template('scan.html')

# --- Config Paths and Helper Functions ---
CONFIG_DIR = Path('test_configs')

def load_test_configs():
    print("DEBUG: load_test_configs called")
    print('[DEBUG] Entering load_test_configs')
    configs = {}
    if CONFIG_DIR.exists():
        print(f'[DEBUG] Found config dir: {CONFIG_DIR}')
        for config_file in CONFIG_DIR.glob('*.json'):
            print(f'[DEBUG] Loading config file: {config_file}')
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_name = config_file.stem
                    configs[config_name] = json.load(f)
                print(f'[DEBUG] Loaded config: {config_file}')
            except Exception as e:
                print(f"Error loading config {config_file}: {e}")
    print('[DEBUG] Returning configs from load_test_configs')
    return configs


# Ensure required directories exist
REQUIRED_DIRS = [
    'uploads',
    'static',
    'static/debug',
    'static/preview',
    'templates',
    'test_configs'
]
for directory in REQUIRED_DIRS:
    Path(directory).mkdir(parents=True, exist_ok=True)

@app.route('/')
def index():
    """Home page - redirect to simple scan."""
    return render_template('simple_scan.html')

@app.route('/simple_scan')
def simple_scan_page():
    """Simple scan page."""
    return render_template('simple_scan.html')

@app.route('/teacher_verification')
def teacher_verification_page():
    """Teacher verification page for reviewing scan results."""
    return render_template('teacher_verification.html')

@app.route('/db_teacher_verification')
def db_teacher_verification():
    """Page to display teacher verification report from the database."""
    return render_template('db_teacher_verification.html')

@app.route('/api/test_configs', methods=['GET'])
def get_test_configs():
    """API endpoint to get all test configurations - returns base test names only."""
    try:
        # Return base test configs (without grade suffixes)
        configs = load_test_configs()
        return jsonify(configs)
    except Exception as e:
        print(f"Error getting test configs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/simple_scan', methods=['POST'])
def api_simple_scan():
    import time
    t0 = time.time()
    print("DEBUG: api_simple_scan called")
    """API endpoint for simple bubble sheet scanning."""
    try:
        # Get uploaded file and test selection
        t1 = time.time(); print(f"[TIMING] File/params received: {t1-t0:.2f}s")
        if 'sheet_file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['sheet_file']
        test_name = request.form.get('template_name') or request.form.get('test_name')
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not test_name:
            return jsonify({'error': 'No test configuration selected'}), 400
        t2 = time.time(); print(f"[TIMING] Params validated: {t2-t0:.2f}s")
        # Load test configuration using grade mapping
        grade_mapping_file = Path('grade_to_config_mapping.json')
        base_config_name = test_name  # Default to the test_name itself
        if grade_mapping_file.exists():
            with open(grade_mapping_file, 'r') as f:
                grade_mapping = json.load(f)
                base_config_name = grade_mapping.get(test_name, test_name)
        configs = load_test_configs()
        if base_config_name not in configs:
            return jsonify({'error': f'Test configuration "{base_config_name}" not found'}), 400
        config = configs[base_config_name]
        t3 = time.time(); print(f"[TIMING] Config loaded: {t3-t0:.2f}s")
        # Parse answer key string into object format
        def parse_answer_key(answer_key_str):
            """Parse answer key string like '1:A, 2:B, 3:C' into object like {1: 'A', 2: 'B', 3: 'C'}"""
            if not answer_key_str or not isinstance(answer_key_str, str):
                return {}
            
            answer_key = {}
            pairs = answer_key_str.split(', ')
            for pair in pairs:
                pair = pair.strip()
                if not pair or ':' not in pair:
                    continue
                parts = pair.split(':', 1)
                if len(parts) >= 2:
                    question, answer = parts[0], parts[1]
                    try:
                        answer_key[int(question.strip())] = answer.strip()
                    except ValueError:
                        continue  # Skip invalid question numbers
            return answer_key

        # Get answer key if available (try grade-specific first, then base)
        t4 = time.time(); print(f"[TIMING] Answer key loaded: {t4-t0:.2f}s")
        answer_key_str = ""  # Initialize as empty string instead of None
        try:
            keys_file = Path('answer_keys_with_grades.json')
            if keys_file.exists():
                with open(keys_file, 'r') as f:
                    keys_data = json.load(f)
                    answer_key_str = keys_data.get(test_name, "")  # Default to empty string
                    # Fallback to original answer keys if grade-specific not found
                    if not answer_key_str:
                        keys_file = Path('answer_keys.json')
                        if keys_file.exists():
                            with open(keys_file, 'r') as f:
                                keys_data = json.load(f)
                                answer_key_str = keys_data.get(base_config_name, "")  # Default to empty string
        except Exception as e:
            print(f"Error loading answer key: {e}")
            answer_key_str = ""  # Ensure it's always a string
        
        # Ensure answer_key_str is always a string (never None)
        if answer_key_str is None:
            answer_key_str = ""
        
        # Parse answer key into object format for JavaScript
        parsed_answer_key = parse_answer_key(answer_key_str)
        
        # Clean up old debug images before processing
        debug_dir = Path('static/debug_images')
        if debug_dir.exists():
            for old_debug in debug_dir.glob('*.png'):
                try:
                    old_debug.unlink()
                    print(f"[DEBUG] Cleaned up old debug image: {old_debug}")
                except Exception as e:
                    print(f"[DEBUG] Could not delete {old_debug}: {e}")
        else:
            debug_dir.mkdir(parents=True, exist_ok=True)
        t5 = time.time(); print(f"[TIMING] Debug images cleaned: {t5-t0:.2f}s")
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = Path(app.config['UPLOAD_FOLDER']) / filename
        file.save(temp_path)
        t6 = time.time(); print(f"[TIMING] File saved: {t6-t0:.2f}s")
        
        try:
            t7 = time.time(); print(f"[TIMING] About to process image(s): {t7-t0:.2f}s")
            import cv2
            from scanner import BubbleSheetScanner
            # Create scanner 
            scanner = BubbleSheetScanner(config)
            static_path = str(Path(app.root_path) / 'static')
            results = []
            # Read and process image(s)
            if filename.lower().endswith('.pdf'):
                import time
                total_start = time.time()
                # Handle PDF files - process all pages in parallel using ProcessPoolExecutor
                try:
                    import fitz  # PyMuPDF
                    from concurrent.futures import ProcessPoolExecutor, as_completed
                    import pickle
                    pdf_document = fitz.open(str(temp_path))
                    page_count = pdf_document.page_count
                    # Save each page as PNG bytes to pass to subprocesses
                    page_pngs = []
                    for page_num in range(page_count):
                        page = pdf_document[page_num]
                        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom
                        pix = page.get_pixmap(matrix=mat)
                        img_data = pix.tobytes("png")
                        page_pngs.append(img_data)
                    pdf_document.close()
                    t8 = time.time(); print(f"[TIMING] PDF pages rendered: {t8-t0:.2f}s")
                    # Prepare arguments for each process
                    proc_args = [
                        (page_num, img_data, config, static_path, parsed_answer_key, answer_key_str, test_name)
                        for page_num, img_data in enumerate(page_pngs)
                    ]
                    # Use 2 workers to match your CPU core count
                    with ProcessPoolExecutor(max_workers=2) as executor:
                        futures = [executor.submit(process_page_proc, arg) for arg in proc_args]
                        page_results = [None] * page_count
                        for future in as_completed(futures):
                            page_num, result = future.result()
                            page_results[page_num] = result
                        results.extend(page_results)
                    t9 = time.time(); print(f"[TIMING] PDF pages processed: {t9-t0:.2f}s")
                except ImportError:
                    return jsonify({'error': 'PDF processing not available. Install PyMuPDF.'}), 500
            else:
                # Handle single image files
                image = cv2.imread(str(temp_path))
                t8 = time.time(); print(f"[TIMING] Image loaded: {t8-t0:.2f}s")
                if image is None:
                    return jsonify({'error': 'Could not read image file'}), 400
                result = scanner.process_image_data(image, static_path, 1, {})
                t9 = time.time(); print(f"[TIMING] Image processed: {t9-t0:.2f}s")
                results.append({
                    'answers': result.get('answers', []),
                    'debug_image_url': result.get('debug_image_url'),
                    'error': result.get('error'),
                    'answerKey': parsed_answer_key,  # Object format for teacher verification
                    'answer_key': answer_key_str,    # String format for scanning page compatibility
                    'testName': test_name,  # Add the test name here
                    'tiebreaker_questions': config.get('tiebreaker_questions', [])  # Pass tiebreaker info
                })
            t10 = time.time(); print(f"[TIMING] All processing done: {t10-t0:.2f}s")
            return jsonify({'results': results})
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
        
    except Exception as e:
        import traceback
        print(f"Error in simple scan: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys', methods=['GET'])
def get_answer_keys():
    """API endpoint to get answer keys for a specific session."""
    try:
        session_name = request.args.get('session', '')
        keys = {}
        
        # Try to load grade-specific keys first
        grade_keys_file = Path('answer_keys_with_grades.json')
        if grade_keys_file.exists():
            with open(grade_keys_file, 'r', encoding='utf-8') as f:
                all_keys = json.load(f)
                # Get keys for this session
                if session_name and session_name in all_keys:
                    keys.update(all_keys[session_name])
        
        # Also load original keys as fallback
        keys_file = Path('answer_keys.json')
        if keys_file.exists():
            with open(keys_file, 'r', encoding='utf-8') as f:
                all_original_keys = json.load(f)
                # Get keys for this session from original file
                if session_name and session_name in all_original_keys:
                    original_keys = all_original_keys[session_name]
                    # Only add keys that don't already exist (grade-specific takes priority)
                    for k, v in original_keys.items():
                        if k not in keys:
                            keys[k] = v
        
        return jsonify(keys)
    except Exception as e:
        print(f"Error getting answer keys: {e}")
        return jsonify({}), 500

@app.route('/api/keys', methods=['POST'])
def save_answer_key():
    """API endpoint to save answer key for a specific session."""
    try:
        data = request.get_json()
        test_name = data.get('test_name')
        key_string = data.get('key_string')
        session_name = data.get('session', '')
        
        if not test_name:
            return jsonify({"error": "Test name is required"}), 400
        
        if not session_name:
            return jsonify({"error": "Session name is required"}), 400
        
        # Determine which file to save to based on test name
        if " - " in test_name and ("Grade" in test_name or "Grades" in test_name):
            # This is a grade-specific test, save to grade-specific file
            keys_file = Path('answer_keys_with_grades.json')
        else:
            # This is a base test, save to original file
            keys_file = Path('answer_keys.json')
        
        # Load existing keys (all sessions)
        if keys_file.exists():
            with open(keys_file, 'r', encoding='utf-8') as f:
                all_keys = json.load(f)
        else:
            all_keys = {}
        
        # Ensure session exists in structure
        if session_name not in all_keys:
            all_keys[session_name] = {}
        
        # Update key for this session
        all_keys[session_name][test_name] = key_string
        
        # Save keys
        with open(keys_file, 'w', encoding='utf-8') as f:
            json.dump(all_keys, f, indent=4)
        
        return jsonify({"message": f"Answer key for '{test_name}' saved successfully"})
        
    except Exception as e:
        print(f"Error saving answer key: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files."""
    return send_from_directory('static', filename)

# --- Database API Routes ---
@app.route('/api/save_scan', methods=['POST'])
def save_scan():
    """Save scan results to database"""
    try:
        data = request.json
        session = SessionLocal()
        
        # Extract student ID to determine grade and school
        student_id = data.get('student_id', '')
        grade = student_id[0] if student_id else ''
        school_code = student_id[1:4] if len(student_id) >= 4 else ''
        
        # Create scan result
        result = ScanResult(
            student_id=student_id,
            test_name=data.get('test_name'),
            grade=grade,
            school=school_code,
            session_name=data.get('session_name'),
            score=data.get('score'),
            correct_count=data.get('correct_count', 0),
            incorrect_count=data.get('incorrect_count', 0),
            tiebreaker_correct=data.get('tiebreaker_correct', 0)
        )
        
        # Store answers and answer key as JSON
        if 'answers' in data:
            result.set_answers(data['answers'])
        if 'answer_key' in data:
            result.set_answer_key(data['answer_key'])
        
        session.add(result)
        session.commit()
        result_id = result.id
        session.close()
        
        return jsonify({'status': 'success', 'id': result_id})
    except Exception as e:
        print(f"Error saving scan: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save_scan_batch', methods=['POST'])
def save_scan_batch():
    """Save multiple scan results at once"""
    try:
        data = request.json
        results = data.get('results', [])
        
        session = SessionLocal()
        saved_count = 0
        
        for scan_data in results:
            student_id = scan_data.get('student_id', '')
            grade = student_id[0] if student_id else ''
            school_code = student_id[1:4] if len(student_id) >= 4 else ''
            
            result = ScanResult(
                student_id=student_id,
                test_name=scan_data.get('test_name'),
                grade=grade,
                school=school_code,
                session_name=scan_data.get('session_name'),
                score=scan_data.get('score'),
                correct_count=scan_data.get('correct_count', 0),
                incorrect_count=scan_data.get('incorrect_count', 0),
                tiebreaker_correct=scan_data.get('tiebreaker_correct', 0)
            )
            
            if 'answers' in scan_data:
                result.set_answers(scan_data['answers'])
            if 'answer_key' in scan_data:
                result.set_answer_key(scan_data['answer_key'])
            
            session.add(result)
            saved_count += 1
        
        session.commit()
        session.close()
        
        return jsonify({'status': 'success', 'saved_count': saved_count})
    except Exception as e:
        print(f"Error saving batch: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_results')
def get_results():
    """Retrieve all scan results from database"""
    try:
        session = SessionLocal()
        results = session.query(ScanResult).order_by(ScanResult.scan_date.desc()).all()
        
        output = []
        for r in results:
            output.append({
                'id': r.id,
                'student_id': r.student_id,
                'studentId': r.student_id,  # Alias for compatibility
                'test_name': r.test_name,
                'testName': r.test_name,  # Alias for compatibility
                'grade': r.grade,
                'school': r.school,
                'session_name': r.session_name,
                'score': r.score,
                'correct': r.correct_count,
                'incorrect': r.incorrect_count,
                'tiebreaker_correct': r.tiebreaker_correct,
                'answers': r.get_answers(),
                'answerKey': r.get_answer_key(),
                'scan_date': r.scan_date.isoformat() if r.scan_date else None
            })
        
        session.close()
        return jsonify(output)
    except Exception as e:
        print(f"Error retrieving results: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_results_by_test/<test_name>')
def get_results_by_test(test_name):
    """Retrieve results for a specific test"""
    try:
        session = SessionLocal()
        results = session.query(ScanResult).filter_by(test_name=test_name).order_by(ScanResult.student_id).all()
        
        output = []
        for r in results:
            output.append({
                'id': r.id,
                'student_id': r.student_id,
                'studentId': r.student_id,
                'test_name': r.test_name,
                'testName': r.test_name,
                'grade': r.grade,
                'school': r.school,
                'score': r.score,
                'correct': r.correct_count,
                'incorrect': r.incorrect_count,
                'tiebreaker_correct': r.tiebreaker_correct,
                'answers': r.get_answers(),
                'answerKey': r.get_answer_key(),
                'scan_date': r.scan_date.isoformat() if r.scan_date else None
            })
        
        session.close()
        return jsonify(output)
    except Exception as e:
        print(f"Error retrieving results for test: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_sessions')
def get_sessions():
    """Get list of all unique session names from both database and school list file"""
    try:
        session_set = set()
        
        # Get sessions from database
        db_session = SessionLocal()
        db_sessions = db_session.query(ScanResult.session_name).distinct().all()
        for s in db_sessions:
            if s[0]:
                session_set.add(s[0])
        db_session.close()
        
        # Get sessions from school list file
        school_list_file = Path('school_list.json')
        if school_list_file.exists():
            try:
                with open(school_list_file, 'r', encoding='utf-8') as f:
                    school_data = json.load(f)
                    # Keys in school_list.json are session names
                    for session_name in school_data.keys():
                        if session_name:
                            session_set.add(session_name)
            except Exception as e:
                print(f"Error reading school list file: {e}")
        
        # Get sessions from answer keys files
        for keys_file in ['answer_keys.json', 'answer_keys_with_grades.json']:
            keys_path = Path(keys_file)
            if keys_path.exists():
                try:
                    with open(keys_path, 'r', encoding='utf-8') as f:
                        keys_data = json.load(f)
                        # Keys might be session names (nested structure)
                        for key in keys_data.keys():
                            if isinstance(keys_data[key], dict):
                                # This is a session with nested keys
                                session_set.add(key)
                except Exception as e:
                    print(f"Error reading {keys_file}: {e}")
        
        # Return sorted list
        session_list = sorted(list(session_set))
        return jsonify(session_list)
    except Exception as e:
        print(f"Error retrieving sessions: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    print("Starting Bubble Sheet Scanner...")
    print("Make sure you have installed the required packages:")
    print("  pip install flask opencv-python numpy PyMuPDF")
    print("\nAccess the application at: http://localhost:5001")
    # --- DEBUG: Print all registered routes at startup ---
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(rule)
    app.run(debug=True, host='0.0.0.0', port=5001)

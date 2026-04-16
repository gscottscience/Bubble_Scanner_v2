import os
from scanner import BubbleSheetScanner
import fitz  # PyMuPDF
import cv2
import numpy as np

def detect_bubbles_and_id(filepath, return_debug=False, config=None, page_num=1):
    """
    Thin wrapper: loads image (from PDF or PNG), instantiates BubbleSheetScanner, and calls process_image_data.
    Returns: (student_id, bubbles, debug_image_url, answers) if return_debug else (student_id, bubbles)
    """
    if config is None:
        raise Exception('Config must be provided by caller (app.py)')
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        doc = fitz.open(filepath)
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).copy()
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    else:
        img = cv2.imread(filepath)
    if img is None:
        raise Exception('Could not load image')
    scanner = BubbleSheetScanner(config)
    # Use the main process_image_data method for all detection and overlays
    result = scanner.process_image_data(img, static_path='static', page_num=page_num, answer_key={})
    if return_debug:
        return {
            'student_id': result.get('student_id'),
            'id_bubbles': []  # Optionally fill with detected bubble coordinates if needed
        }, img, result.get('debug_image_url'), result.get('answers', [])
    else:
        return {
            'student_id': result.get('student_id'),
            'id_bubbles': []
        }, img

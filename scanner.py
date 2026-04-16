import base64
import logging
import typing as t
import os

import cv2
import numpy as np
logger = logging.getLogger(__name__)

class BubbleSheetScanner:
    def grade_answers(self, answers, answer_key):
        """
        Grade answers: only count as incorrect if a filled answer is present and it is wrong.
        Blanks ('', None, '--') are ignored and do not count as incorrect.
        Returns (correct, incorrect)
        """
        correct = 0
        incorrect = 0
        for q_num, student_answer in answers.items():
            key_answer = answer_key.get(str(q_num), None)
            if key_answer is not None:
                if student_answer in [None, '', '--']:
                    continue  # Do not count blank answers as incorrect
                if student_answer == key_answer:
                    correct += 1
                else:
                    incorrect += 1
        return correct, incorrect

    def __init__(self, template_config):
        self.template_config = template_config
        self.student_id_roi = template_config.get('student_id_roi')
        self.student_id_threshold = template_config.get('student_id_threshold', 0.7)
        self.answer_columns = template_config.get('answer_columns', [])
        # Area thresholds for corner square detection (adjust as needed)
        self.min_corner_square_area = 100
        self.max_corner_square_area = 2000
        self.bubble_threshold = template_config.get('bubble_threshold', 0.7)
        self.bubble_intensity_threshold = template_config.get('bubble_intensity_threshold', 205)
        self.num_questions = template_config.get('num_questions', 0)
        self.tiebreaker_questions = template_config.get('tiebreaker_questions', [])
        self.circle_params = template_config.get('circle_params', {})
        # Add any other config fields as needed
        # Legacy/compatibility fields
        self.answers_roi_col1 = template_config.get('answers_roi_col1')
        self.answers_roi_col2_upper = template_config.get('answers_roi_col2_upper')
        self.answers_roi_col2_lower = template_config.get('answers_roi_col2_lower')

    def is_point_in_roi(self, x: int, y: int, roi: t.Tuple[int, int, int, int]) -> bool:
        roi_x, roi_y, roi_width, roi_height = roi
        return roi_x <= x <= roi_x + roi_width and roi_y <= y <= roi_y + roi_height

    def get_bubble_intensity(self, image: "NDArray", x: int, y: int, r: int) -> float:
        mask = np.zeros_like(image)
        cv2.circle(mask, (x, y), r, 255, -1)
        bubble_region = cv2.bitwise_and(image, image, mask=mask)
        return cv2.mean(bubble_region, mask=mask)[0]

    def is_filled_bubble(self, image: "NDArray", x: int, y: int, r: int,
                        threshold: float = None) -> bool:
        if threshold is None:
            threshold = self.bubble_threshold
        mean_intensity = self.get_bubble_intensity(image, x, y, r)
        return mean_intensity < threshold * 255

    def map_student_id(self, detected_answers: t.List[t.Tuple[int, int, int]],
                      gray_image: "NDArray", debug_image: "NDArray") -> str:
        student_id_str = []
        roi_x, roi_y, roi_width, roi_height = self.student_id_roi
        num_cols = 4
        num_rows = 10

        # Calculate column and row dimensions based on the ROI
        col_width = roi_width / num_cols
        row_height = roi_height / num_rows

        # 1. Find all filled bubbles within the main student_id_roi first
        id_bubbles = []
        print("[DEBUG] --- Student ID Bubble Candidates ---")
        for x, y, r in detected_answers:
            if self.is_point_in_roi(x, y, self.student_id_roi):
                intensity = self.get_bubble_intensity(gray_image, x, y, r)
                print(f"[DEBUG] Bubble at ({x},{y},{r}) intensity: {intensity:.2f} filled: {self.is_filled_bubble(gray_image, x, y, r, threshold=self.student_id_threshold)}")
                if self.is_filled_bubble(gray_image, x, y, r, threshold=self.student_id_threshold):
                    id_bubbles.append({'x': x, 'y': y, 'r': r, 'intensity': intensity})
                    # Mark all filled bubbles in red for debug
                    cv2.circle(debug_image, (x, y), r, (0, 0, 255), 2)

        # Print min/max rel_x for all filled bubbles
        if id_bubbles:
            rel_xs = [(b['x'] - roi_x) / col_width for b in id_bubbles]
            print(f"[DEBUG] rel_x for all filled bubbles: {rel_xs}")
            print(f"[DEBUG] min rel_x: {min(rel_xs):.2f}, max rel_x: {max(rel_xs):.2f}")
        else:
            print("[DEBUG] No filled bubbles detected in Student ID ROI.")

        # Print column boundaries
        col_bounds = [roi_x + i * col_width for i in range(num_cols + 1)]
        print(f"[DEBUG] Column boundaries (x): {col_bounds}")

        # 2. Assign columns by x-position within the ROI (robust to extra/missing bubbles)
        column_groups: t.List[t.List[t.Dict]] = [[] for _ in range(num_cols)]
        if id_bubbles:
            for bubble in id_bubbles:
                rel_x = (bubble['x'] - roi_x) / col_width
                col_index = int(rel_x)
                if col_index < 0:
                    col_index = 0
                elif col_index >= num_cols:
                    col_index = num_cols - 1
                column_groups[col_index].append(bubble)
                rel_y = (bubble['y'] - roi_y) / row_height
                row_index = int((bubble['y'] - roi_y) // row_height)
                print(f"[DEBUG] Bubble at ({bubble['x']},{bubble['y']}) assigned to col_index={col_index} intensity: {bubble['intensity']:.2f} rel_x={rel_x:.2f} rel_y={rel_y:.2f} row_index={row_index}")
                cv2.circle(debug_image, (bubble['x'], bubble['y']), min(bubble['r'], 12), (0, 255, 255), 1)
                cv2.putText(debug_image, f"C{col_index}R{row_index}", (bubble['x']-10, bubble['y']-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        else:
            print("[DEBUG] No filled bubbles to assign to columns.")

        # 3. Process each column group to find the darkest bubble and determine the digit

        for col_idx, col_group in enumerate(column_groups):
            if not col_group:
                # Always pick a digit: if no bubbles, pick closest to center of column
                print(f"[DEBUG] Column {col_idx}: No bubbles found, defaulting to row 0.")
                student_id_str.append('0')
                continue

            print(f"[DEBUG] Column {col_idx}: Candidates:")
            for b in col_group:
                rel_y = (b['y'] - roi_y) / row_height
                print(f"    Bubble at ({b['x']},{b['y']}) intensity: {b['intensity']:.2f} rel_y={rel_y:.2f}")

            # Always pick the darkest bubble in the column
            darkest_bubble = min(col_group, key=lambda b: b['intensity'])
            
            # Correctly calculate the row_index based on the bubble's y-position within the ROI
            rel_y = (darkest_bubble['y'] - roi_y) / row_height
            row_index = int(rel_y)
            if row_index < 0:
                row_index = 0
            elif row_index >= num_rows:
                row_index = num_rows - 1

            print(f"[DEBUG] Column {col_idx}: Selected (darkest) bubble at ({darkest_bubble['x']},{darkest_bubble['y']}) intensity: {darkest_bubble['intensity']:.2f} rel_y={rel_y:.2f} row_index={row_index}")

            if 0 <= row_index < num_rows:
                best_digit = row_index
                student_id_str.append(str(best_digit))
                # Draw the selected bubble in blue and label digit
                cv2.circle(debug_image, (darkest_bubble['x'], darkest_bubble['y']), darkest_bubble['r'], (255, 0, 0), 2)
                cv2.putText(debug_image, str(best_digit), (darkest_bubble['x']+10, darkest_bubble['y']), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            else:
                # If out of bounds, default to 0
                student_id_str.append('0')
                print(f"[DEBUG] Column {col_idx}: Selected bubble out of row bounds, defaulting to 0.")

        print(f"[DEBUG] Final Student ID: {''.join(student_id_str)}")
        return "".join(student_id_str)

    def map_answers(self, detected_answers: t.List[t.Tuple[int, int, int]],
                   gray_image: "NDArray", debug_image: "NDArray",
                   roi: t.Tuple[int, int, int, int],
                   start_q: int, end_q: int,
                   answer_type: str = 'A-E',
                   num_choices: int = None,
                   question_types: t.Dict[str, t.Union[str, t.Dict]] = None) -> t.List[t.Dict]:
        import time
        t0 = time.perf_counter()
        # Defensive checks
        if detected_answers is None:
            detected_answers = []
        if debug_image is None or gray_image is None:
            print(f"[DEBUG] map_answers: debug_image or gray_image is None, returning empty list")
            return []
        roi_x, roi_y, _, _ = roi
        # Vectorize detected_answers to numpy array for fast filtering
        if detected_answers:
            arr = np.array(detected_answers)
            # Filter bubbles inside ROI
            mask = (
                (arr[:,0] >= roi_x) & (arr[:,0] <= roi_x + roi[2]) &
                (arr[:,1] >= roi_y) & (arr[:,1] <= roi_y + roi[3])
            )
            roi_relative_answers = arr[mask]
            roi_relative_answers = np.column_stack((roi_relative_answers[:,0] - roi_x, roi_relative_answers[:,1] - roi_y, roi_relative_answers[:,2]))
            roi_relative_answers = roi_relative_answers.tolist()
        else:
            roi_relative_answers = []
        print(f"[DEBUG] map_answers: Processing {len(roi_relative_answers)} bubbles passed into the function for ROI {roi}")
        """
        Map detected answer bubbles to questions for a given ROI/grid.
        Ensures all indentation is correct and logic is clear.
        """
        print(f"[DEBUG] Expected answer positions:")
        num_rows = end_q - start_q + 1
        # For Art Part B, always use 4 columns (A-D) for mixed type
        template_name = self.template_config.get('template_name', '').lower()
        is_art = 'art' in template_name and 'part b' in template_name
        
        if answer_type == 'A-D':
            max_answer_choices = ['A', 'B', 'C', 'D']
        elif answer_type == 'mixed':
            # If num_choices is explicitly provided, use it for physical layout
            if num_choices is not None:
                if num_choices == 4:
                    max_answer_choices = ['A', 'B', 'C', 'D']
                elif num_choices == 2:
                    max_answer_choices = ['T', 'F']
                elif num_choices == 5:
                    max_answer_choices = ['A', 'B', 'C', 'D', 'E']
                else:
                    max_answer_choices = ['A', 'B', 'C', 'D', 'E']
            # For Art Part B (any grade), mixed type uses A-D layout
            elif is_art:
                max_answer_choices = ['A', 'B', 'C', 'D']
            else:
                max_answer_choices = ['A', 'B', 'C', 'D', 'E']
        elif answer_type == 'A-E':
            max_answer_choices = ['A', 'B', 'C', 'D', 'E']
        elif answer_type == 'A-H':
            max_answer_choices = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        elif answer_type == 'T/F' or answer_type == 'T-F':
            max_answer_choices = ['T', 'F']
        else:
            max_answer_choices = ['A', 'B', 'C', 'D', 'E']
        row_height = roi[3] / num_rows
        col_width = roi[2] / len(max_answer_choices)
        # Precompute expected column centers for all columns
        expected_centers = np.array([(col_width * col) + (col_width / 2) for col in range(len(max_answer_choices))])

        # Print expected answer positions
        t1 = time.perf_counter(); print(f"[TIMING] Setup and filtering: {t1-t0:.4f}s")
        print(f"[DEBUG] question_types available: {question_types is not None}, keys: {list(question_types.keys()) if question_types else 'None'}")
        for q_idx in range(num_rows):
            q_num = start_q + q_idx
            # Get answer choices for this specific question
            if question_types and str(q_num) in question_types:
                q_type_data = question_types[str(q_num)]
                print(f"[DEBUG_OLD] Q{q_num} type_data: {q_type_data}")
                if isinstance(q_type_data, dict):
                    q_type = q_type_data.get('type', 'A-D')
                else:
                    q_type = q_type_data
                if q_type == 'T-F':
                    question_answer_choices = ['T', 'F']
                    print(f"[DEBUG_OLD] Q{q_num} set to T/F")
                elif q_type == 'A-E':
                    question_answer_choices = ['A', 'B', 'C', 'D', 'E']
                elif q_type == 'A-D':
                    question_answer_choices = ['A', 'B', 'C', 'D']
                else:
                    question_answer_choices = max_answer_choices
            else:
                question_answer_choices = max_answer_choices
            expected_y = (row_height * q_idx) + (row_height / 2)
            for col_idx in range(len(question_answer_choices)):
                expected_x = (col_width * col_idx) + (col_width / 2)
                print(f"    Q{q_num} {question_answer_choices[col_idx]}: ({int(expected_x)}, {int(expected_y)})")

        # --- NEW: Student ID-style "darkest bubble wins" logic for answer regions ---
        answers = {}
        print(f"[DEBUG] --- map_answers for ROI {roi}, Q{start_q}-{end_q}, type {answer_type} ---")
        print(f"[DEBUG] Detected answers: {detected_answers}")
        
        # For each question row, find all bubbles and pick the darkest one

        template_name = self.template_config.get('template_name', '').lower()

        for q_idx in range(num_rows):
            q_num = start_q + q_idx
            row_top = row_height * q_idx
            row_bottom = row_height * (q_idx + 1)

            # Determine question-specific answer choices
            if question_types and str(q_num) in question_types:
                q_type_data = question_types[str(q_num)]
                if isinstance(q_type_data, dict):
                    q_type = q_type_data.get('type', 'A-D')
                else:
                    q_type = q_type_data
                print(f"[DEBUG] Q{q_num}: type={q_type}, data={q_type_data}")
                if q_type == 'T-F':
                    question_answer_choices = ['T', 'F']
                    print(f"[DEBUG] Q{q_num}: Set to T/F")
                elif q_type == 'A-E':
                    question_answer_choices = ['A', 'B', 'C', 'D', 'E']
                elif q_type == 'A-D':
                    question_answer_choices = ['A', 'B', 'C', 'D']
                else:
                    # Default to max_answer_choices, but trim to number specified if present
                    if isinstance(q_type_data, dict) and 'choices' in q_type_data:
                        question_answer_choices = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][:q_type_data['choices']]
                    else:
                        question_answer_choices = max_answer_choices
            else:
                # Force A-D only for Art Part B if no specific question type
                if is_art:
                    question_answer_choices = ['A', 'B', 'C', 'D']
                else:
                    question_answer_choices = max_answer_choices
            
            # Always use max column spacing for physical layout, but only map to valid choices
            # This handles cases where T/F questions use the first 2 columns of a 4-column layout
            question_col_width = roi[2] / len(max_answer_choices)
            question_expected_centers = np.array([(question_col_width * col) + (question_col_width / 2) for col in range(len(max_answer_choices))])

            # Find all bubbles in this question row
            row_bubbles = []
            all_bubbles_in_row = [] # For debugging all bubbles regardless of threshold
            if roi_relative_answers:
                arr = np.array(roi_relative_answers)
                cy = arr[:,1]
                row_mask = (cy >= row_top) & (cy <= row_bottom)
                row_bubble_arr = arr[row_mask]
                if row_bubble_arr.shape[0] > 0:
                    cx = row_bubble_arr[:,0]
                    cy = row_bubble_arr[:,1]
                    r = row_bubble_arr[:,2]
                    global_x = cx + roi[0]
                    global_y = cy + roi[1]
                    intensities = [self.get_bubble_intensity(gray_image, int(gx), int(gy), int(rad)) for gx, gy, rad in zip(global_x, global_y, r)]
                    distances = np.abs(cx[:,None] - question_expected_centers[None,:])
                    col_indices = np.argmin(distances, axis=1)
                    # Map to answer choices, but only for columns that have valid answers for this question
                    # For T/F, only columns 0 and 1 are valid (T, F)
                    # For A-D, columns 0-3 are valid (A, B, C, D)
                    answer_choices = []
                    for idx in col_indices:
                        if idx < len(question_answer_choices):
                            answer_choices.append(question_answer_choices[idx])
                        else:
                            answer_choices.append(None)  # Invalid column for this question type
                    for i in range(row_bubble_arr.shape[0]):
                        if answer_choices[i] is None:
                            continue  # skip invalid columns
                        bubble_data = {
                            'x': cx[i], 'y': cy[i], 'r': r[i],
                            'intensity': intensities[i],
                            'col_idx': col_indices[i],
                            'answer': answer_choices[i]
                        }
                        # Only keep one bubble per answer choice (darkest)
                        existing = next((b for b in all_bubbles_in_row if b['answer'] == bubble_data['answer']), None)
                        if existing is None or bubble_data['intensity'] < existing['intensity']:
                            if existing:
                                all_bubbles_in_row.remove(existing)
                            all_bubbles_in_row.append(bubble_data)
            t2 = time.perf_counter(); print(f"[TIMING] Row {q_num} mapping: {t2-t1:.4f}s"); t1 = t2

            # Now filter for valid candidates based on intensity threshold
            # Use the configured threshold (not forcing minimum of 245)
            tuned_threshold = self.bubble_intensity_threshold
            background_intensity = np.median([b['intensity'] for b in all_bubbles_in_row]) if all_bubbles_in_row else 255
            for bubble in all_bubbles_in_row:
                print(f"[DEBUG] Q{q_num} bubble '{bubble['answer']}' intensity: {bubble['intensity']:.2f} (threshold: {tuned_threshold}, background: {background_intensity:.2f})")
                # Only count as filled if darker than background and below threshold (reduced from 20 to 10)
                if bubble['intensity'] < tuned_threshold and (background_intensity - bubble['intensity'] > 10):
                    row_bubbles.append(bubble)

            # Debug print all bubbles found in the row
            if all_bubbles_in_row:
                print(f"[DEBUG] Q{q_num}: All bubbles found in row: " + ", ".join([f"{b['answer']}({b['intensity']:.1f})" for b in all_bubbles_in_row]))

            # For Art Part B, if no filled bubble in row, output '--' (do not count as incorrect)
            if is_art:
                if row_bubbles:
                    darkest_bubble = min(row_bubbles, key=lambda b: b['intensity'])
                    answers[q_num] = darkest_bubble['answer']
                    cv2.circle(debug_image, 
                              (int(darkest_bubble['x'] + roi[0]), int(darkest_bubble['y'] + roi[1])), 
                              int(darkest_bubble['r']), (0, 255, 0), 2)
                    # Draw blue label for selected bubble only
                    label = f"Q{q_num}{darkest_bubble['answer']}"
                    cv2.putText(debug_image, label, (int(darkest_bubble['x'] + roi[0] + darkest_bubble['r']), int(darkest_bubble['y'] + roi[1] - darkest_bubble['r'])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                    print(f"[DEBUG] Q{q_num}: Candidates below threshold ({self.bubble_intensity_threshold}): {[b['answer'] for b in row_bubbles]}. Selected answer '{darkest_bubble['answer']}' with intensity {darkest_bubble['intensity']:.2f}")
                else:
                    answers[q_num] = '--'
                    print(f"[DEBUG][Art 6] Q{q_num}: No filled bubbles, output '--'")
            else:
                if row_bubbles:
                    darkest_bubble = min(row_bubbles, key=lambda b: b['intensity'])
                    answers[q_num] = darkest_bubble['answer']
                    cv2.circle(debug_image, 
                              (int(darkest_bubble['x'] + roi[0]), int(darkest_bubble['y'] + roi[1])), 
                              int(darkest_bubble['r']), (0, 255, 0), 2)
                    # Draw blue label for selected bubble only
                    label = f"Q{q_num}{darkest_bubble['answer']}"
                    cv2.putText(debug_image, label, (int(darkest_bubble['x'] + roi[0] + darkest_bubble['r']), int(darkest_bubble['y'] + roi[1] - darkest_bubble['r'])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                    print(f"[DEBUG] Q{q_num}: Candidates below threshold ({self.bubble_intensity_threshold}): {[b['answer'] for b in row_bubbles]}. Selected answer '{darkest_bubble['answer']}' with intensity {darkest_bubble['intensity']:.2f}")
                else:
                    print(f"[DEBUG] Q{q_num}: No bubbles found in row below intensity threshold {self.bubble_intensity_threshold}")
        # Always output all questions, even if no answer detected
        output = []
        for q_num in range(start_q, end_q + 1):
            ans = answers.get(q_num, "--")
            output.append({"question": q_num, "answer": ans})
        return output

    def correct_orientation(self, image: "NDArray", page_num: int, debug=False) -> t.Tuple[t.Optional["NDArray"], t.Optional[str]]:
        debug_img = None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape
        debug_img = image.copy()
        # Adjust thresholding to handle inverted images
        # Try both normal and inverted threshold, pick the one with more contours
        import numpy as np
        def ensure_bgr(img):
            if img is None or img.size == 0:
                return None
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if len(img.shape) == 3 and img.shape[2] == 3:
                img = np.ascontiguousarray(img)
                if img.dtype != np.uint8:
                    img = img.astype(np.uint8)
                if img.shape[0] > 0 and img.shape[1] > 0:
                    return img
            return None

        # gray and img_h, img_w already set above
        _, thresh_inv = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed_inv = cv2.morphologyEx(thresh_inv, cv2.MORPH_CLOSE, kernel, iterations=2)
        # Find contours in the thresholded image
        contours, _ = cv2.findContours(closed_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # closed_normal and contours_normal may need to be defined above if not present
        # ...rest of the method logic should be indented here...
        # Visualize region boundaries on debug image
        # Expand regions to cover extreme corners
        regions = {
            'tl': (0, 0, int(img_w * 0.20), int(img_h * 0.20)),
            'tr': (int(img_w * 0.80), 0, img_w, int(img_h * 0.20)),
            'bl': (0, int(img_h * 0.80), int(img_w * 0.20), img_h),
            'br': (int(img_w * 0.80), int(img_h * 0.80), img_w, img_h)
        }
        region_candidates = {k: [] for k in regions}
        region_colors = {'tl': (255,0,0), 'tr': (0,255,255), 'br': (0,255,0), 'bl': (255,0,255)}
        for k, (rx0, ry0, rx1, ry1) in regions.items():
            if debug_img is not None:
                cv2.rectangle(debug_img, (rx0, ry0), (rx1, ry1), region_colors[k], 2)
        print(f"[DEBUG] Region boundaries drawn on debug image.")
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
            if len(approx) == 4:
                (x, y, w, h) = cv2.boundingRect(approx)
                aspect_ratio = w / float(h) if h > 0 else 0
                centroid = (x + w // 2, y + h // 2)
                # Loosen area and aspect ratio constraints
                area_ok = self.min_corner_square_area * 0.2 < area < self.max_corner_square_area * 3
                aspect_ok = 0.3 <= aspect_ratio <= 3.0
                region = None
                for k, (rx0, ry0, rx1, ry1) in regions.items():
                    if rx0 <= centroid[0] < rx1 and ry0 <= centroid[1] < ry1:
                        region = k
                if region:
                    region_candidates[region].append((area, approx))
                print(f"[DEBUG] Contour area: {area}, aspect ratio: {aspect_ratio:.2f}, centroid: {centroid}, region: {region}, area_ok: {area_ok}, aspect_ok: {aspect_ok}, accepted: {area_ok and aspect_ok and region}")
                if debug_img is not None:
                    cv2.drawContours(debug_img, [approx], -1, (128,128,128), 1)
        # Print all candidate centroids for each region
        for region_name, candidates in region_candidates.items():
            centroids = []
            for area, approx in candidates:
                M = cv2.moments(approx)
                if M['m00'] != 0:
                    centroids.append((int(M['m10'] / M['m00']), int(M['m01'] / M['m00'])))
                if debug_img is not None:
                    cv2.drawContours(debug_img, [approx], -1, (128,128,128), 1)
            print(f"[DEBUG] Region {region_name} candidate centroids: {centroids}")
        # ...existing code...
        # Pick best candidate (largest area) from each region and highlight it
        corner_squares = []
        # Select outermost candidate for each region
        for k in ['tl', 'tr', 'br', 'bl']:
            candidates = region_candidates[k]
            if candidates:
                # Get centroid for each candidate
                candidate_centroids = []
                for area, approx in candidates:
                    M = cv2.moments(approx)
                    if M['m00'] != 0:
                        candidate_centroids.append((approx, (int(M['m10'] / M['m00']), int(M['m01'] / M['m00']))))
                # Select outermost based on region
                if k == 'tl':
                    # Top-left: smallest x + smallest y
                    best = min(candidate_centroids, key=lambda tup: tup[1][0] + tup[1][1])[0]
                elif k == 'tr':
                    # Top-right: largest x - smallest y
                    best = max(candidate_centroids, key=lambda tup: tup[1][0] - tup[1][1])[0]
                elif k == 'br':
                    # Bottom-right: largest x + largest y
                    best = max(candidate_centroids, key=lambda tup: tup[1][0] + tup[1][1])[0]
                elif k == 'bl':
                    # Bottom-left: smallest x - largest y
                    best = min(candidate_centroids, key=lambda tup: tup[1][0] - tup[1][1])[0]
                corner_squares.append(best)
                # Highlight selected square for each region with thicker border and marker
                if debug_img is not None:
                    cv2.drawContours(debug_img, [best], -1, region_colors[k], 4)
                    # Draw centroid marker
                    M = cv2.moments(best)
                    if M['m00'] != 0:
                        cx = int(M['m10'] / M['m00'])
                        cy = int(M['m01'] / M['m00'])
                        cv2.circle(debug_img, (cx, cy), 10, (0,0,255), -1)
                        cv2.putText(debug_img, k, (cx-20, cy-20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)
        print(f"[DEBUG] Number of accepted corner squares (one per region): {len(corner_squares)}")
        if len(corner_squares) == 4:
            # Sort the corners into top-left, top-right, bottom-right, bottom-left
            centroids = []
            for square in corner_squares:
                M = cv2.moments(square)
                centroids.append((int(M['m10'] / M['m00']), int(M['m01'] / M['m00'])))
            rect = np.zeros((4, 2), dtype="float32")
            s = np.sum(centroids, axis=1)
            rect[0] = centroids[np.argmin(s)] # Top-left has smallest sum
            rect[2] = centroids[np.argmax(s)] # Bottom-right has largest sum
            diff = np.diff(centroids, axis=1)
            rect[1] = centroids[np.argmin(diff)] # Top-right has smallest difference
            rect[3] = centroids[np.argmax(diff)] # Bottom-left has largest difference
            (tl, tr, br, bl) = rect
            # Draw corner circles/labels on the original image before warping
            image = ensure_bgr(image)
            for idx, (name, pt) in enumerate(zip(['tl','tr','br','bl'], [tl, tr, br, bl])):
                if image is not None:
                    cv2.circle(image, (int(pt[0]), int(pt[1])), 12, (0,0,255), 3)
                    cv2.putText(image, name, (int(pt[0])-20, int(pt[1])-20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)
            # Print the coordinates of the detected corners
            print(f"[DEBUG] Sorted corners: tl={tl}, tr={tr}, br={br}, bl={bl}")
            # Compute the width and height of the new warped image
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))
            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))
            # Define the destination points for the perspective transform
            dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
            # Compute the perspective transform matrix and apply it
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
            # Crop a small margin to remove edge artifacts
            # Keep top and side margins unchanged to preserve ROI coordinates
            # Use much larger negative bottom margin to give substantial room for bottom questions
            top_margin = 10
            bottom_margin = -30
            side_margin = 10
            cropped = warped[top_margin:maxHeight-bottom_margin, side_margin:maxWidth-side_margin]
            # Ensure cropped image is valid (non-empty, 3 channels)
            def ensure_bgr(img):
                import numpy as np
                if img is None or img.size == 0:
                    return None
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                if len(img.shape) == 3 and img.shape[2] == 1:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                if len(img.shape) == 3 and img.shape[2] == 3:
                    img = np.ascontiguousarray(img)
                    if img.dtype != np.uint8:
                        img = img.astype(np.uint8)
                    if img.shape[0] > 0 and img.shape[1] > 0:
                        return img
                return None

            valid_cropped = ensure_bgr(cropped)
            if valid_cropped is not None:
                print(f"[DEBUG] Cropped and aligned image to {valid_cropped.shape}")
                return valid_cropped, None
            valid_warped = ensure_bgr(warped)
            if valid_warped is not None:
                print("[DEBUG] Cropped image invalid, using warped image instead.")
                return valid_warped, None
            print("[DEBUG] Both cropped and warped images invalid, returning blank image.")
            blank = np.zeros((800, 1200, 3), dtype=np.uint8)
            return blank, None
        else:
            logger.warning(f"Detected {len(corner_squares)} corners, expected 4. Skipping orientation correction.")
            # Save the debug image with drawn candidate squares
            debug_thresh_filename = f"corner_debug_sheet_{page_num}.png"
            debug_thresh_path = os.path.join("static", "debug_images", debug_thresh_filename)
            os.makedirs(os.path.dirname(debug_thresh_path), exist_ok=True)
            cv2.imwrite(debug_thresh_path, debug_img)
            logger.info(f"Saved corner detection debug image to {debug_thresh_path}")
            debug_url = f"/static/debug_images/{debug_thresh_filename}"
            return None, debug_url

    def draw_template_rois(self, image_np: "NDArray", perspective_matrix: t.Optional["NDArray"] = None) -> "NDArray":
        """Draws the configured ROIs (student ID and answer regions) onto a given image using the current config structure."""
        debug_image = image_np.copy()
        print(f"[DEBUG] draw_template_rois: image shape={debug_image.shape}, dtype={debug_image.dtype}")
        def transform_roi(roi, M):
            pts = np.array([
                [roi[0], roi[1]],
                [roi[0] + roi[2], roi[1]],
                [roi[0] + roi[2], roi[1] + roi[3]],
                [roi[0], roi[1] + roi[3]]
            ], dtype="float32")
            pts = np.array([pts])
            warped_pts = cv2.perspectiveTransform(pts, M)[0]
            x_min, y_min = np.min(warped_pts, axis=0)
            x_max, y_max = np.max(warped_pts, axis=0)
            w = x_max - x_min
            h = y_max - y_min
            return [int(x_min), int(y_min), int(w), int(h)]

        # Draw student ID ROI (magenta)
        student_id_roi = None
        if 'student_id_config' in self.template_config and 'student_id_roi' in self.template_config['student_id_config']:
            student_id_roi = self.template_config['student_id_config']['student_id_roi']
            if perspective_matrix is not None:
                student_id_roi = transform_roi(student_id_roi, perspective_matrix)
            # Defensive check: ensure ROI is within image bounds
            img_h, img_w = debug_image.shape[:2]
            x, y, w, h = [int(c) for c in student_id_roi]
            if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                print(f"[WARNING] Student ID ROI {student_id_roi} out of bounds for image shape {debug_image.shape}")
            else:
                _draw_roi(debug_image, student_id_roi, (255, 0, 255), "Student ID", rows=10, cols=4)
                print(f"[DEBUG] Drew Student ID ROI: {student_id_roi}")

        # Always use answer_columns for overlays
        if hasattr(self, 'answer_columns') and self.answer_columns:
            for idx, col in enumerate(self.answer_columns):
                roi = col['roi']
                label = col.get('label', f"Col{idx+1}")
                rows = col.get('end_q', 1) - col.get('start_q', 1) + 1
                choices = col.get('choices', 5)
                if perspective_matrix is not None:
                    roi = transform_roi(roi, perspective_matrix)
                img_h, img_w = debug_image.shape[:2]
                x, y, w, h = [int(c) for c in roi]
                if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                    print(f"[WARNING] Answer ROI {roi} (label={label}) out of bounds for image shape {debug_image.shape}")
                else:
                    print(f"[DEBUG] About to draw ROI: {roi} label: {label} rows: {rows} cols: {choices}")    
                    _draw_roi(debug_image, roi, (0, 165, 255), f"{label}", rows=rows, cols=choices)
                    print(f"[DEBUG] Drew Answer ROI: {roi} label: {label} rows: {rows} cols: {choices}")
        else:
            print("[DEBUG] No answer_columns found for overlay drawing.")
        return debug_image

    def process_image_data(self, image_np: "NDArray", static_path: str, page_num: int, answer_key: t.Dict[int, str]) -> t.Dict:
        debug_image = image_np.copy()  # Always initialize debug_image
        """Process the image data (as a numpy array) and extract answers."""
        import cv2
        import datetime
        import numpy as np
        import os
        # Always use the absolute static path for debug images
        ABS_DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'debug_images')
        REL_DEBUG_DIR = '/static/debug_images/'
        os.makedirs(ABS_DEBUG_DIR, exist_ok=True)
        try:
            print(f"[DEBUG] [process_image_data] Starting for page {page_num}")
            oriented_image, corner_debug_url = self.correct_orientation(image_np, page_num=page_num, debug=False)
            if oriented_image is None:
                print(f"[DEBUG] [process_image_data] Orientation failed for page {page_num}")
                # debug_image already set to image_np.copy() above
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(debug_image, "Orientation failed", (50, 100), font, 1.2, (0,0,255), 3, cv2.LINE_AA)
                debug_image_filename = f"bubble_debug_sheet_{page_num}_fail.png"
                debug_image_path = os.path.join(ABS_DEBUG_DIR, debug_image_filename)
                cv2.imwrite(debug_image_path, debug_image)
                return {
                    "sheet": page_num,
                    "answers": [],
                    "student_id": None,
                    "debug_image_url": f"{REL_DEBUG_DIR}{debug_image_filename}",
                    "error": "Could not detect 4 corner squares for orientation."
                }
            try:
                print(f"[DEBUG] [process_image_data] Orientation succeeded for page {page_num}")
                print(f"[DEBUG] Configuration loaded: {self.template_config.get('name', 'Unknown')}")
                print(f"[DEBUG] Student ID ROI: {self.student_id_roi}")
                print(f"[DEBUG] Answer columns type: {type(self.answer_columns)}")
                print(f"[DEBUG] Answer columns: {self.answer_columns}")
                print(f"[DEBUG] Image shape: {image_np.shape if image_np is not None else 'None'}")
                print(f"[DEBUG] Image type: {type(image_np)}")
                # ...existing code for perspective, ROI, and bubble finding...
                print(f"[DEBUG] About to convert image to grayscale")
                gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
                print(f"[DEBUG] Grayscale conversion successful, shape: {gray.shape}")
                _, thresh_normal = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
                _, thresh_inv = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
                print(f"[DEBUG] Thresholding successful")
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                print(f"[DEBUG] About to apply morphological operations")
                closed_normal = cv2.morphologyEx(thresh_normal, cv2.MORPH_CLOSE, kernel, iterations=2)
                closed_inv = cv2.morphologyEx(thresh_inv, cv2.MORPH_CLOSE, kernel, iterations=2)
                print(f"[DEBUG] About to find contours")
                contours_normal, _ = cv2.findContours(closed_normal.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours_inv, _ = cv2.findContours(closed_inv.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                print(f"[DEBUG] Found {len(contours_normal)} normal contours, {len(contours_inv)} inverted contours")
                if len(contours_inv) > len(contours_normal):
                    closed_thresh = closed_inv
                    contours = contours_inv
                    print(f"[DEBUG] Using inverted contours: {len(contours)} contours")
                else:
                    closed_thresh = closed_normal
                    contours = contours_normal
                    print(f"[DEBUG] Using normal contours: {len(contours)} contours")
                print(f"[DEBUG] About to get image dimensions")
                img_h, img_w = closed_thresh.shape
                print(f"[DEBUG] Image dimensions: {img_w}x{img_h}")
                print(f"[DEBUG] About to create regions dict")
                regions = {
                    'tl': (0, 0, int(img_w * 0.20), int(img_h * 0.20)),
                    'tr': (int(img_w * 0.80), 0, img_w, int(img_h * 0.20)),
                    'bl': (0, int(img_h * 0.80), int(img_w * 0.20), img_h),
                    'br': (int(img_w * 0.80), int(img_h * 0.80), img_w, img_h)
                }
                print(f"[DEBUG] About to create region_candidates")
                region_candidates = {k: [] for k in regions}
                print(f"[DEBUG] About to iterate over contours, type: {type(contours)}, contours is None: {contours is None}")
                if contours is None:
                    print(f"[DEBUG] ERROR: contours is None!")
                    contours = []
                print(f"[DEBUG] Starting contour iteration loop")
                for i, contour in enumerate(contours):
                    print(f"[DEBUG] Processing contour {i+1}/{len(contours)}")
                    if contour is None:
                        print(f"[DEBUG] ERROR: Contour {i+1} is None!")
                        continue
                    area = cv2.contourArea(contour)
                    perimeter = cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
                    if len(approx) == 4:
                        (x, y, w, h) = cv2.boundingRect(approx)
                        aspect_ratio = w / float(h) if h > 0 else 0
                        centroid = (x + w // 2, y + h // 2)
                        area_ok = self.min_corner_square_area * 0.2 < area < self.max_corner_square_area * 3
                        aspect_ok = 0.3 <= aspect_ratio <= 3.0
                        region = None
                        print(f"[DEBUG] About to iterate regions, type: {type(regions)}, regions is None: {regions is None}")
                        if regions is None:
                            print(f"[DEBUG] ERROR: regions is None!")
                            regions = {}
                        for k, (rx0, ry0, rx1, ry1) in regions.items():
                            if rx0 <= centroid[0] < rx1 and ry0 <= centroid[1] < ry1:
                                region = k
                        if region:
                            region_candidates[region].append((area, approx))
                print(f"[DEBUG] Contour loop completed, processing corner squares")
                print(f"[DEBUG] Region candidates: {[(k, len(v)) for k, v in region_candidates.items()]}")
                corner_squares = []
                for k in ['tl', 'tr', 'br', 'bl']:
                    print(f"[DEBUG] Processing region {k}")
                    candidates = region_candidates[k]
                    print(f"[DEBUG] Region {k} has {len(candidates) if candidates else 'None'} candidates")
                    if candidates:
                        candidate_centroids = []
                        print(f"[DEBUG] Processing {len(candidates)} candidates for region {k}")
                        for i, (area, approx) in enumerate(candidates):
                            print(f"[DEBUG] Processing candidate {i+1}, approx type: {type(approx)}, approx is None: {approx is None}")
                            if approx is None:
                                print(f"[DEBUG] ERROR: approx is None for candidate {i+1}")
                                continue
                            M = cv2.moments(approx)
                            if M['m00'] != 0:
                                candidate_centroids.append((approx, (int(M['m10'] / M['m00']), int(M['m01'] / M['m00']))) )
                        print(f"[DEBUG] Region {k} has {len(candidate_centroids)} valid centroids")
                        if len(candidate_centroids) == 0:
                            print(f"[DEBUG] WARNING: No valid centroids for region {k}, skipping")
                            continue
                        print(f"[DEBUG] Selecting best candidate for region {k}")
                        if k == 'tl':
                            best = min(candidate_centroids, key=lambda tup: tup[1][0] + tup[1][1])[0]
                        elif k == 'tr':
                            best = max(candidate_centroids, key=lambda tup: tup[1][0] - tup[1][1])[0]
                        elif k == 'br':
                            best = max(candidate_centroids, key=lambda tup: tup[1][0] + tup[1][1])[0]
                        elif k == 'bl':
                            best = min(candidate_centroids, key=lambda tup: tup[1][0] - tup[1][1])[0]
                        print(f"[DEBUG] Selected best candidate for region {k}")
                        corner_squares.append(best)
                print(f"[DEBUG] Total corner squares found: {len(corner_squares)}")
                if len(corner_squares) == 4:
                    centroids = []
                    for square in corner_squares:
                        M = cv2.moments(square)
                        centroids.append((int(M['m10'] / M['m00']), int(M['m01'] / M['m00'])))
                    rect = np.zeros((4, 2), dtype="float32")
                    s = np.sum(centroids, axis=1)
                    rect[0] = centroids[np.argmin(s)] # Top-left
                    rect[2] = centroids[np.argmax(s)] # Bottom-right
                    diff = np.diff(centroids, axis=1)
                    rect[1] = centroids[np.argmin(diff)] # Top-right
                    rect[3] = centroids[np.argmax(diff)] # Bottom-left
                    (tl, tr, br, bl) = rect
                    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                    maxWidth = max(int(widthA), int(widthB))
                    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
                    maxHeight = max(int(heightA), int(heightB))
                    dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
                    M = cv2.getPerspectiveTransform(rect, dst)
                else:
                    M = None
                    print(f"[DEBUG] Not enough corner squares, M set to None")
                # --- Transform ROIs for frontend overlay ---
                def transform_roi(roi, M):
                    print(f"[DEBUG] transform_roi called, M is None: {M is None}")
                    pts = np.array([
                        [roi[0], roi[1]],
                        [roi[0] + roi[2], roi[1]],
                        [roi[0] + roi[2], roi[1] + roi[3]],
                        [roi[0], roi[1] + roi[3]]
                    ], dtype="float32")
                    pts = np.array([pts])
                    warped_pts = cv2.perspectiveTransform(pts, M)[0]
                    x_min, y_min = np.min(warped_pts, axis=0)
                    x_max, y_max = np.max(warped_pts, axis=0)
                    w = x_max - x_min
                    h = y_max - y_min
                    return [int(x_min), int(y_min), int(w), int(h)]
                if M is not None:
                    student_id_roi_xformed = transform_roi(self.student_id_roi, M)
                    answers_roi_col1_xformed = transform_roi(self.answers_roi_col1, M)
                    answers_roi_col2_upper_xformed = transform_roi(self.answers_roi_col2_upper, M) if hasattr(self, 'answers_roi_col2_upper') else None
                    answers_roi_col2_lower_xformed = transform_roi(self.answers_roi_col2_lower, M) if hasattr(self, 'answers_roi_col2_lower') else None
                else:
                    student_id_roi_xformed = list(self.student_id_roi) if self.student_id_roi is not None else None
                    answers_roi_col1_xformed = list(self.answers_roi_col1) if self.answers_roi_col1 is not None else None
                    answers_roi_col2_upper_xformed = list(self.answers_roi_col2_upper) if hasattr(self, 'answers_roi_col2_upper') and self.answers_roi_col2_upper is not None else None
                    answers_roi_col2_lower_xformed = list(self.answers_roi_col2_lower) if hasattr(self, 'answers_roi_col2_lower') and self.answers_roi_col2_lower is not None else None
                # Always draw the student ID ROI grid (purple) before any detection
                debug_image = oriented_image.copy()
                print(f"[DEBUG] About to draw ROIs. self.student_id_roi: {self.student_id_roi}")
                print(f"[DEBUG] self.answer_columns: {self.answer_columns}")
                
                if self.student_id_roi is not None:
                    _draw_roi(debug_image, self.student_id_roi, (255, 0, 255), "Student ID", rows=10, cols=4)
                else:
                    print(f"[DEBUG] student_id_roi is None!")
                
                # Draw all answer ROIs as well for context  
                if self.answer_columns is not None:
                    for col in self.answer_columns:
                        if col is not None and 'roi' in col:
                            _draw_roi(debug_image, col['roi'], (255, 165, 0), col.get('label', 'Answer'), rows=col.get('end_q', 0) - col.get('start_q', 0) + 1, cols=col.get('choices', 0))
                        else:
                            print(f"[DEBUG] Column is None or missing 'roi': {col}")
                else:
                    print(f"[DEBUG] answer_columns is None!")
                gray_image = cv2.cvtColor(oriented_image, cv2.COLOR_BGR2GRAY)
                blurred_gray = cv2.medianBlur(gray_image, 5)
                adaptive_thresh = cv2.adaptiveThreshold(
                    blurred_gray, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 11, 2
                )
                # --- Detect bubbles in Student ID ROI ---
                sid_roi = self.student_id_roi
                sid_x, sid_y, sid_w, sid_h = sid_roi
                sid_crop = adaptive_thresh[sid_y:sid_y+sid_h, sid_x:sid_x+sid_w]
                # Save sid_crop for debug
                sid_crop_debug_path = os.path.join("static", "debug_images", f"sid_crop_{page_num}.png")
                try:
                    cv2.imwrite(sid_crop_debug_path, sid_crop)
                    print(f"[DEBUG] Saved sid_crop image to {sid_crop_debug_path}")
                except Exception as crop_save_err:
                    print(f"[DEBUG] Could not save sid_crop image: {crop_save_err}")
                sid_circles = None
                detected_sid_bubbles = []
                try:
                    sid_circles = cv2.HoughCircles(sid_crop, cv2.HOUGH_GRADIENT, **self.circle_params)
                    print(f"[DEBUG] sid_circles result: {sid_circles}")
                except Exception as hough_err:
                    logger.error(f"HoughCircles error in student ID ROI: {hough_err}")
                if sid_circles is not None:
                    try:
                        sid_circles = np.uint16(np.around(sid_circles))
                        for circle in sid_circles[0, :]:
                            x, y, r = int(circle[0]), int(circle[1]), int(circle[2])
                            detected_sid_bubbles.append((x+sid_x, y+sid_y, r))
                            # Use a different color to avoid confusion with answer bubbles
                            cv2.circle(debug_image, (x+sid_x, y+sid_y), min(r, 12), (255, 255, 0), 2)  # Yellow circles for detected SID bubbles
                    except Exception as sid_bubble_err:
                        logger.error(f"Error processing detected student ID circles: {sid_bubble_err}")
                else:
                    logger.warning(f"No circles detected in student ID ROI for page {page_num}.")
                # Ensure detected_sid_bubbles is always a list
                if detected_sid_bubbles is None:
                    detected_sid_bubbles = []
                # Student ID grid info
                student_id_rows = 10
                student_id_cols = 4
                try:
                    student_id = self.map_student_id(detected_sid_bubbles if detected_sid_bubbles is not None else [], gray_image, debug_image)
                except Exception as sid_map_err:
                    logger.error(f"Error mapping student ID: {sid_map_err}")
                    student_id = None
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(debug_image, f"Student ID error: {sid_map_err}", (50, 150), font, 1.0, (0,0,255), 2, cv2.LINE_AA)

                # --- Detect bubbles in each answer ROI and map answers ---
                all_answers = []
                print(f"[DEBUG] Starting answer column processing, self.answer_columns: {self.answer_columns}")
                
                if self.answer_columns is None:
                    print(f"[DEBUG] ERROR: self.answer_columns is None!")
                    raise ValueError("self.answer_columns is None")
                
                for col_idx, col in enumerate(self.answer_columns):
                    print(f"[DEBUG] Processing column {col_idx}: {col}")
                    if col is None:
                        print(f"[DEBUG] ERROR: Column {col_idx} is None!")
                        continue
                    
                    roi = col['roi']
                    start_q = col['start_q']
                    end_q = col['end_q']
                    answer_type = col.get('type', 'A-E')
                    num_choices = col.get('choices', None)
                    x, y, w, h = roi
                    # Crop the ROI from the original (aligned) grayscale image for intensity analysis
                    roi_gray = gray_image[y:y+h, x:x+w]
                    roi_thresh = adaptive_thresh[y:y+h, x:x+w]
                    ans_circles = None
                    detected_ans_bubbles = []
                    try:
                        ans_circles = cv2.HoughCircles(roi_thresh, cv2.HOUGH_GRADIENT, **self.circle_params)
                    except Exception as hough_ans_err:
                        logger.error(f"HoughCircles error in answer ROI {roi}: {hough_ans_err}")
                    if ans_circles is not None:
                        try:
                            ans_circles = np.uint16(np.around(ans_circles))
                            for circle in ans_circles[0, :]:
                                cx, cy, cr = int(circle[0]), int(circle[1]), int(circle[2])
                                # Map to full image coordinates
                                gx, gy = cx + x, cy + y
                                detected_ans_bubbles.append((gx, gy, cr))
                                # Draw all detected bubbles in orange for debug
                                cv2.circle(debug_image, (gx, gy), cr, (0, 128, 255), 2)
                        except Exception as ans_bubble_err:
                            logger.error(f"Error processing detected answer circles in ROI {roi}: {ans_bubble_err}")
                    else:
                        logger.warning(f"No circles detected in answer ROI {roi} for page {page_num}.")
                    # Use the same intensity-based logic as Student ID for filled detection
                    try:
                        # Get question_types from column first, then fall back to template config root level
                        question_types = col.get('question_types', None) or self.template_config.get('question_types', None)
                        mapped_answers = self.map_answers(detected_ans_bubbles if detected_ans_bubbles is not None else [], gray_image, debug_image, roi, start_q, end_q, answer_type=answer_type, num_choices=num_choices, question_types=question_types)
                        if mapped_answers is not None:
                            all_answers.extend(mapped_answers)
                        else:
                            print(f"[DEBUG] map_answers returned None for ROI {roi}")
                    except Exception as ans_map_err:
                        logger.error(f"Error mapping answers in ROI {roi}: {ans_map_err}")
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        cv2.putText(debug_image, f"Answer mapping error: {ans_map_err}", (50, 200 + 30 * self.answer_columns.index(col)), font, 1.0, (0,0,255), 2, cv2.LINE_AA)
            except Exception as bubble_error:
                logger.error(f"Error during bubble processing after failed orientation: {bubble_error}")
                # Always draw overlays and error message on the current debug_image (with purple grid)
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(debug_image, f"Bubble processing error: {bubble_error}", (50, 100), font, 1.2, (0,0,255), 3, cv2.LINE_AA)
                debug_thresh_filename = f"bubble_debug_sheet_{page_num}_fail.png"
                debug_path = os.path.join("static", "debug_images", debug_thresh_filename)
                cv2.imwrite(debug_path, debug_image)
                return {
                    "sheet": page_num,
                    "answers": [],
                    "student_id": None,
                    "debug_image_url": f"/static/debug_images/{debug_thresh_filename}",
                    "error": f"Bubble processing error: {bubble_error}"
                }
            # all_answers is already built above
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            debug_image_filename = f"bubble_debug_sheet_{page_num}_{timestamp}.png"
            debug_image_path = os.path.join(ABS_DEBUG_DIR, debug_image_filename)
            print(f"[DEBUG] Saving debug image for page {page_num} to {debug_image_path} (shape={debug_image.shape}, dtype={debug_image.dtype})")
            cv2.imwrite(debug_image_path, debug_image)
            if 'answers_roi_col2_upper_xformed' not in locals():
                answers_roi_col2_upper_xformed = None
            if 'answers_roi_col2_lower_xformed' not in locals():
                answers_roi_col2_lower_xformed = None
            return {
                "sheet": page_num,
                "student_id": student_id,
                "answers": all_answers,
                "debug_image_url": f"{REL_DEBUG_DIR}{debug_image_filename}",
                "error": None
            }
        except Exception as e:
            print(f"Sheet {page_num}: Error processing image - {e}")
            debug_image = image_np.copy()
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(debug_image, f"Fatal error: {e}", (50, 100), font, 1.2, (0,0,255), 3, cv2.LINE_AA)
            debug_image_filename = f"bubble_debug_sheet_{page_num}_fatal.png"
            debug_image_path = os.path.join(ABS_DEBUG_DIR, debug_image_filename)
            cv2.imwrite(debug_image_path, debug_image)
            return {
                "sheet": page_num,
                "answers": [],
                "student_id": None,
                "debug_image_url": f"{REL_DEBUG_DIR}{debug_image_filename}",
                "error": f"Error processing image: {e}"
            }

def _draw_roi(image, roi, color, label, rows=1, cols=1):
    """Helper function to draw ROI rectangles and grids on an image."""
    import cv2
    x, y, w, h = roi
    
    # Draw main ROI rectangle
    cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
    
    # Draw label
    cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    # Draw grid lines
    if rows > 1:
        row_height = h / rows
        for i in range(1, rows):
            y_line = y + int(i * row_height)
            cv2.line(image, (x, y_line), (x + w, y_line), color, 1)
    
    if cols > 1:
        col_width = w / cols
        for i in range(1, cols):
            x_line = x + int(i * col_width)
            cv2.line(image, (x_line, y), (x_line, y + h), color, 1)

def parse_answer_key(answer_key_str):
    """
    Parse an answer key string like '1. B, 2. D, 3. C, ...' into a dict {1: 'B', 2: 'D', ...}
    Also supports '1:A, 2:B, 3:C' format
    """
    answer_key = {}
    if not answer_key_str:
        return answer_key
    for part in answer_key_str.split(','):
        part = part.strip()
        if not part:
            continue
        # Support both ':' and '.' separators
        if ':' in part:
            qnum, ans = part.split(':', 1)
        elif '.' in part:
            qnum, ans = part.split('.', 1)
        else:
            continue
        try:
            qnum = int(qnum.strip())
            ans = ans.strip().upper()
            answer_key[qnum] = ans
        except Exception:
            continue
    return answer_key

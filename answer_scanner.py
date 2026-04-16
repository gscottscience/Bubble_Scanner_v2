import cv2
import numpy as np

# Utility to parse ROI string from CSV (e.g., 'Col1: 123,765,330,1190; Col2: 710,777,330,345')
def parse_answer_rois(roi_string):
    rois = {}
    if not roi_string or not isinstance(roi_string, str):
        return rois
    for part in roi_string.split(';'):
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            parts = part.split(':', 1)
            if len(parts) >= 2:
                label, coords_str = parts[0], parts[1]
                try:
                    coords = [int(x.strip()) for x in coords_str.split(',')]
                    if len(coords) >= 4:  # Ensure we have x, y, w, h
                        rois[label.strip()] = coords  # [x, y, w, h]
                except ValueError:
                    continue  # Skip invalid coordinate sets
    return rois

# Extract answer regions from image using ROI info from template dict
def extract_answer_regions(image, template_dict):
    import numpy as np
    if isinstance(image, list):
        print("[DEBUG] [answer_scanner] Converting image from list to np.array")
        image = np.array(image)
    print(f"[DEBUG] [answer_scanner] image shape after conversion: {getattr(image, 'shape', None)}")
    if not (hasattr(image, 'ndim') and image.ndim >= 2):
        raise ValueError(f"Image is not at least 2D after conversion: type={type(image)}, shape={getattr(image, 'shape', None)}")
    roi_string = template_dict.get('Answer ROI(s) (x,y,w,h)')
    if not roi_string:
        raise ValueError('No ROI string found in template_dict')
    rois = parse_answer_rois(roi_string)
    regions = {}
    def flatten_roi(val):
        # Recursively flatten
        if isinstance(val, (list, tuple)) and len(val) == 1 and isinstance(val[0], (list, tuple)):
            return flatten_roi(val[0])
        if isinstance(val, (list, tuple)) and any(isinstance(i, (list, tuple)) for i in val):
            flat = []
            for i in val:
                if isinstance(i, (list, tuple)):
                    flat.extend(flatten_roi(i))
                else:
                    flat.append(i)
            return flat
        return val
    for label, roi_val in rois.items():
        print(f"[DEBUG] [answer_scanner] ROI for label {label}: {roi_val}")
        roi_val = flatten_roi(roi_val)
        print(f"[DEBUG] [answer_scanner] ROI for label {label} after flatten: {roi_val}")
        if not (isinstance(roi_val, (list, tuple)) and len(roi_val) == 4 and all(isinstance(x, int) for x in roi_val)):
            raise ValueError(f"ROI for label {label} is not a flat list of 4 ints: {roi_val}")
        x, y, w, h = roi_val
        print(f"[DEBUG] [answer_scanner] image type: {type(image)}")
        print(f"[DEBUG] [answer_scanner] x={x} ({type(x)}), y={y} ({type(y)}), w={w} ({type(w)}), h={h} ({type(h)})")
        if not hasattr(image, '__getitem__'):
            raise TypeError(f"Image is not subscriptable: type={type(image)}")
        crop = image[y:y+h, x:x+w]
        regions[label] = crop
    return regions  # dict: label -> cropped image region

# Example usage:
# from answer_scanner import extract_answer_regions
# regions = extract_answer_regions(image, template_dict)
# Now you can run bubble detection on each region as needed.

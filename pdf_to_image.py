import sys
import os
from pdf2image import convert_from_path

if len(sys.argv) < 2:
    print("Usage: python3 pdf_to_image.py <input.pdf> [output.png]")
    sys.exit(1)
pdf_path = sys.argv[1]
output_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(pdf_path)[0] + ".png"
if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
    sys.exit(1)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
images = convert_from_path(pdf_path, first_page=1, last_page=1)
if not images:
    print("No images generated from PDF.")
    sys.exit(1)
images[0].save(output_path, 'PNG')
print(f"Saved first page as: {output_path}")

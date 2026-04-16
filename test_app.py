from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route('/simple_scan', methods=['GET'])
def simple_scan_page():
    return render_template('simple_scan.html')

@app.route('/api/simple_scan', methods=['POST'])
def api_simple_scan():
    file = request.files.get('sheet_file')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400
    # Dummy response for test
    return jsonify({'student_id': '12345', 'bubbles': [1, 2, 3, 4]})

if __name__ == '__main__':
    app.run(debug=True, port=5002)

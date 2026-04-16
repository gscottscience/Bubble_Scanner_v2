from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/test_configs', methods=['GET'])
def get_test_configs():
    return jsonify({"test": "ok"})

if __name__ == '__main__':
    print("Flask minimal app is running")
    app.run(debug=True, port=5001)

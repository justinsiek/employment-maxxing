from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route('/api/double', methods=['GET'])
def double_number():
    number_str = request.args.get('number', default='0', type=str)

    number = int(number_str)
    doubled_number = number * 2
    return jsonify({'result': doubled_number})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
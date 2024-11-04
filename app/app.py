import json

from flask import Flask, request

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/health')
def health():
    return 'Healthy!'


@app.route('/echo', methods=['POST'])
def echo():
    return request.get_json().get('message')


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)

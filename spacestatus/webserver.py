import json

from flask import Flask
from flask import request

app = Flask(__name__)

global msgs
msgs = []

@app.route("/msg", methods=['POST'])
def hello():
    global msgs

    data = request.data
    json_request = json.loads(data)

    msg = json_request['msg']
    if msg:
        msgs.append(str(msg))

    return '{ "status": "ok" }'

def run_server():
    app.run(host='0.0.0.0', port=7645)

def get_msgs():
    global msgs
    msgs_copy = msgs
    msgs = []
    return msgs_copy

if __name__ == "__main__":
    run_server()
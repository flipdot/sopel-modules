import json

from flask import Flask
from flask import request

app = Flask(__name__)

global bot

@app.route("/msg", methods=['POST'])
def hello():
    global bot

    data = request.get_json(force=True, silent=True)
    msg = data['msg']
    if msg and bot:
        bot.say(str(msg))

    return '{ "status": "ok" }'

def run_server(b):
    global bot
    bot = b
    app.run(host='0.0.0.0', port=7645)

if __name__ == "__main__":
    run_server(None)
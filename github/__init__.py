# coding=utf8

import sopel
from sopel import module
import requests
import json
from flask import Flask, request
from thread import start_new_thread

app = Flask(__name__)
local_bot = None

def setup(bot):
    global local_bot
    global app
    local_bot = bot
    start_new_thread(app.run,(),{'port': 3333})

def shutdown(bot):
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        func()


@app.route('/webhook/',methods=['POST'])
def webhook():
    event = request.headers.get('X-GitHub-Event')
    try:
        if event == 'push':
            handle_push_event()
    except Exception as e:
        pass
    return "OK"


def handle_push_event():
    global local_bot
    url = ''
    data = json.loads(request.data)
    r = requests.post("http://git.io", data={'url':data['compare'] })
    if r.status_code == 201:
        url = r.headers['location']
    for c in local_bot.config.core.channels:
        local_bot.msg(c,"[{}] {} pushed {} new commit: {}".format(data['repository']['name'],
                                                                  data['pusher']['name'],
                                                                  len(data['commits']),
                                                                  url))

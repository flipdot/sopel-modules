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
        data = json.loads(request.data)
        if event == 'push':
            handle_push_event(data)
        elif event == 'repository':
            handle_repository_event(data)
    except Exception as e:
        print  e.message
        pass
    return "OK"

def handle_repository_event(data):
    url = github_shortify(data['repository']['html_url'])
    bot_say("{} {} {}  repository: {}".format(data['sender']['login'],
                                              data['action'],
                                              data['repository']['full_name'],
                                              url))


def handle_push_event(data):
    url = github_shortify(data['compare'])
    bot_say("[{}] {} pushed {} new commit{}: {}".format(data['repository']['name'],
                                              data['pusher']['name'],
                                              len(data['commits']),
                                              "s" if (len(data['commits']) > 1) else "",
                                              url))


def github_shortify(url):
    r = requests.post("http://git.io", data={'url':url })
    if r.status_code == 201:
        return r.headers['location']
    return ""

def bot_say(msg):
    global local_bot
    for c in local_bot.config.core.channels:
        local_bot.msg(c,msg)

# coding=utf8

import sopel
from sopel import module
import requests
import json
import hmac
import hashlib
from flask import Flask, request, abort
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
    global local_bot

    event = request.headers.get('X-GitHub-Event')
    try:
        if getattr(local_bot.config, "github", None):
            secret = getattr(local_bot.config.github, "secret", None)
            if secret:
        
	        hash = request.headers.get('X-Hub-Signature')
                digest = hmac.new(secret, "", hashlib.sha1)

                digest.update(request.data)
                hash_calc = "sha1=" + digest.hexdigest()
                if hash_calc != hash:
                    print "expected hash {}; actual hash {}".format(hash_calc, hash)
                    return "Failed", 403
        
        data = json.loads(request.data)
        if event == 'push':
            handle_push_event(data)
        elif event == 'repository':
            handle_repository_event(data)
        elif event == 'issues':
            handle_issue_event()
	elif event == 'status':
            pass
        else:
            handle_unimplemented_event(data, event)
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
def handle_issue_event(data):
    url = github_shortify(data['issue']['html_url'])
    bot_say("[{}] {} {} issue "{}": {}".format(data['repository']['name'],
                                              data['issue']['user']['login'],
                                              data['action'],
                                              data['issue']['title'],
                                              url))



def handle_unimplemented_event(data, event):
    bot_say("unknown github event '{}'".format(event)) 


def github_shortify(url):
    r = requests.post("https://git.io", data={'url':url })
    if r.status_code == 201:
        return r.headers['location']
    return ""

def bot_say(msg):
    global local_bot
    for c in local_bot.config.core.channels:
        local_bot.msg(c,msg)


"""Github module for sopel

Automatically prints information on the repositories by the set up
user/organization.
"""
# Mostly blatantly stolen from
# https://github.com/flipdot/sopel-modules/tree/master/github

import hashlib
import hmac
import json
import re
import requests
import sopel
import threading

from flask import Flask, abort
from pprint import pprint
from sopel import module
from sopel.config.types import FilenameAttribute, StaticSection, ValidatedAttribute


# Colored prefix
#   \x03AA,BB
#   AA = foreground color
#   BB = background color
#   ,BB can be omitted
#
#   For more information
#   https://github.com/myano/jenni/wiki/IRC-String-Formatting
#   http://www.mirc.co.uk/colors.html
COLOR_NETWORK = '\x0302' # blue
COLOR_BOLD    = '\x02'
COLOR_RESET   = '\x0F'
COLOR_PREFIX  = '[%sgit%s]' % (COLOR_NETWORK, COLOR_RESET)

IGNORED_EVENTS = {
    'check_run',
    'check_suite',
    'deployment',
    'deployment_status',
    'fork',
    'label',
    'member',
    'pull_request_review',
    'pull_request_review_comment',
    'repository_vulnerability_alert',
    'star',
    'team',
    'team_add',
    'watch',
}

IGNORED_KEYWORDS = {
    'docker digest',
    'Docker digest',
    'docker tag',
    'Docker tag',
    'renovate',
    'yarn: Upgrade',
}

IGNORED_NICK_PARTS = {
    '[bot]',
}

IGNORED_BRANCH_NAMES = {
    'dependabot',
}

app = Flask(__name__)
bot_global = None
flask_started = False


class GithubSection(StaticSection):
    announce_channel = ValidatedAttribute('announce_channel', default='#ffks')
    announce_commit_messages = ValidatedAttribute('announce_commit_messages ', bool, default=True)
    webhook_secret = ValidatedAttribute('webhook_secret', default='YOUMUSTCHANGETHIS')
    webhook_port = ValidatedAttribute('webhook_port', int, default=3333)


def setup(bot):
    global app, bot_global, flask_started
    bot.config.define_section('github', GithubSection)
    bot_global = bot
    if not flask_started:
        threading.Thread(target=app.run,
                         args=(),
                         kwargs={'port': bot.config.github.webhook_port},
                         ).start()
        flask_started = True


def shutdown(bot):
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        func()


@app.route('/', methods=['POST'])
def webhook():
    global bot_global
    with app.test_request_context():
        from flask import request

    event = request.headers.get('X-GitHub-Event')

    if event in IGNORED_EVENTS:
        return "OK"

    try:
        webhook_secret = bot_global.config.github.webhook_secret
        hash_gh = request.headers.get('X-Hub-Signature')

        try:
            digest = hmac.new(webhook_secret.encode('utf-8'), b"", hashlib.sha1)
        except Exception as err:
            digest = hmac.new(webhook_secret, "", hashlib.sha1)

        digest.update(request.data)
        hash_calc = "sha1=" + digest.hexdigest()
        if hash_calc != hash_gh:
            print("Expected hash: {}\nActual hash: {}".format(hash_calc, hash_gh))
            return "Failed", 403

        data = request.json
        if event == 'create':
            handle_create_event(data)
        elif event == 'delete':
            handle_delete_event(data)
        elif event == 'issues':
            handle_issue_event(data)
        elif event == 'issue_comment':
            handle_issue_comment_event(data)
        elif event == 'push':
            handle_push_event(data)
        elif event == 'repository':
            handle_repository_event(data)
        elif event == 'status':
            pass
        else:
            handle_unimplemented_event(data, event)
    except Exception as e:
        print(e.message)
        pass
    return "OK"


def handle_repository_event(data):
    if data['action'] == "deleted":
        bot_say("{} Repo {}{}{} {} by {}".format(COLOR_PREFIX,
                 COLOR_BOLD,
                 data['repository']['name'],
                 COLOR_RESET,
                 data['action'],
                 data['sender']['login']))
    else:
        url = github_shortify(data['repository']['html_url'])
        bot_say("{} Repo {}{}{} {} by {}: {}".format(COLOR_PREFIX,
                 COLOR_BOLD,
                 data['repository']['name'],
                 COLOR_RESET,
                 data['action'],
                 data['sender']['login'],
                 url))


def handle_push_event(data):
    # Zero commits, e.g. when branch was deleted
    if len(data['commits']) < 1:
        return
    # Filter bad words
    for commit in data['commits']:
        for k in IGNORED_NICK_PARTS:
            if k in commit['author']['name']:
                return
        for k in IGNORED_KEYWORDS:
            if k in commit['message']:
                return
    url = github_shortify(data['compare'])

    # Omit default branch
    branch = re.sub(r"[^/]+/[^/]+/([^/]+)", r"\1", data['ref'])
    if branch == data['repository']['default_branch']:
        branch = ""
    else:
        branch = "/{}".format(branch)
        # Cancel on non-default branch
        return

    bot_say("{} {}{}{}{} {} commit{} pushed by {}: {}".format(COLOR_PREFIX,
             COLOR_BOLD,
             data['repository']['name'],
             COLOR_RESET,
             branch,
             len(data['commits']),
             "s" if (len(data['commits']) > 1) else "",
             data['pusher']['name'],
             url))

    if bot_global.config.github.announce_commit_messages:
        for commit in data['commits']:
            bot_say("      {}".format(commit['message']))


def handle_issue_event(data):
    url = github_shortify(data['issue']['html_url'])
    bot_say("{} [{}] {} {} issue \"{}\": {}".format(COLOR_PREFIX,
             data['repository']['name'],
             data['issue']['sender']['login'],
             data['action'],
             data['issue']['title'],
             url))


def handle_issue_comment_event(data):
    url = github_shortify(data['issue']['html_url'])
    bot_say("{} [{}] {} commented issue \"{}\": {}".format(COLOR_PREFIX,
             data['repository']['name'],
             data['issue']['sender']['login'],
             data['issue']['title'],
             url))


def handle_unimplemented_event(data, event):
    pass


def handle_create_event(data):
    # Filter bad words
    for k in IGNORED_NICK_PARTS:
        if k in data['sender']['login']:
            return
    for k in IGNORED_BRANCH_NAMES:
        if k in data['ref']:
            return
    ref_type = data['ref_type']
    if ref_type == 'branch':
        bot_say("{} Branch {}{}{}/{} created by {}".format(COLOR_PREFIX,
                 COLOR_BOLD,
                 data['repository']['name'],
                 COLOR_RESET,
                 data['ref'],
                 data['sender']['login']))
    else:
        bot_say("{} 'create' action for '{}' not yet implemented".format(COLOR_PREFIX,
                 ref_type))

        # Debug
        print("CREATE")
        pprint(data)
        print("\n\n\n")


def handle_delete_event(data):
    ref_type = data['ref_type']
    if ref_type == 'branch':
        bot_say("{} Branch {}{}{}/{} deleted by {}".format(COLOR_PREFIX,
                 COLOR_BOLD,
                 data['repository']['name'],
                 COLOR_RESET,
                 data['ref'],
                 data['sender']['login']))
    else:
        bot_say("{} 'create' action for '{}' not yet implemented".format(COLOR_PREFIX,
                 ref_type))

        # Debug
        print("CREATE")
        pprint(data)
        print("\n\n\n")


def github_shortify(url):
    r = requests.post("https://git.io", data={'url':url })
    if r.status_code == 201:
        return r.headers['location']
    return ""


def bot_say(msg):
    global bot_global
    for c in bot_global.config.core.channels:
        bot_global.msg(c,msg)

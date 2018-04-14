"""Grafana alerts webhook module for sopel

Accepts authorized webhook alert requests and forms them to messages.
"""

import base64
import threading
import sys
from flask import Flask, abort

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
COLOR_GRAFANA = '\x0303' # green
COLOR_BOLD    = '\x02'
COLOR_RESET   = '\x0F'
COLOR_PREFIX  = '[%sstats%s]' % (COLOR_GRAFANA, COLOR_RESET)

app = Flask(__name__)
bot_global = None
flask_grafana_started = False


class GrafanaSection(StaticSection):
    announce_channel = ValidatedAttribute('announce_channel', default='#flipdot')
    webhook_user = ValidatedAttribute('webhook_user', default='CHANGEUSER')
    webhook_pass = ValidatedAttribute('webhook_pass', default='CHANGEPASS')
    webhook_port = ValidatedAttribute('webhook_port', int, default=4444)


def setup(bot):
    global app, bot_global, flask_grafana_started
    bot.config.define_section('grafana', GrafanaSection)
    bot_global = bot
    if not flask_grafana_started:
        threading.Thread(target=app.run,
                         args=(),
                         kwargs={'port': bot.config.grafana.webhook_port},
                         ).start()
        flask_grafana_started = True


def shutdown(bot):
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        func()


@app.route('/', methods=['POST'])
def webhook():
    global bot_global
    with app.test_request_context():
        from flask import request

    # Authentication
    try:
        auth = request.headers.get('Authorization').split(' ')
        auth_type = auth[0]
        if auth_type != 'Basic':
            raise ValueError('Only basic auth (user/pass) is allowed!\n')
        auth_login = base64.b64decode(auth[1]).decode('utf-8').split(':')
        auth_user = auth_login[0]
        auth_pass = auth_login[1]
        if auth_user != bot_global.config.grafana.webhook_user or auth_pass != bot_global.config.grafana.webhook_pass:
            raise ValueError('Wrong credentials! ({} / {})\n'.format(auth_user, auth_pass))
    except Exception as e:
        sys.stdout.write("\n\nERROR:\n{}\n\n".format(e))
        sys.stdout.flush()
        abort(403)

    # Debug
    # sys.stdout.write("\n\nREQUEST:\n{}\n\nHEADERS:\n{}\n\nJSON:\n{}\n\n".format(request, request.headers, request.json))

    # Create IRC message
    try:
        json = request.json
        msgs = ["{} {}{}{}: {}".format(COLOR_PREFIX, COLOR_BOLD, json.get('ruleName'), COLOR_RESET, json.get('message'))]

        # Only show alerts, not "OK"s and not "no data"s
        # if json.get('state') == 'ok':
        if json.get('state') != 'alerting':
            abort(500)

        # Add numeric reason if available
        if json.get('evalMatches'):
            matches = ''
            for item in json.get('evalMatches'):
                if len(matches) > 1:
                    matches += ', '
                matches += '{}: {}'.format(item.get('metric'), item.get('value'))
            msgs[0] = "{} ({})".format(msgs[0], matches)

        # Add image URL if available
        if json.get('imageUrl'):
            msgs.append("{}{}".format("        ", json.get('imageUrl')))
    except Exception as e:
        sys.stdout.write("\n\nERROR:\n{}\n\n".format(e))
        sys.stdout.flush()
        abort(500)

    for msg in msgs:
        # sys.stdout.write("\n\nMESSAGE:\n{}\n\n".format(msg))
        # sys.stdout.flush()
        bot_say(msg)
    return "OK\n"




def bot_say(msg):
    global bot_global
    bot_global.say(msg, bot_global.config.grafana.announce_channel)

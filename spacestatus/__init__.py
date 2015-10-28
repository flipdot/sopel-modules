# coding=utf8
from __future__ import absolute_import
import sopel
from sopel.module import commands, interval
from sopel import module
import requests
import json

INTERVAL = 60
space_status = None
local_bot = None

def setup(bot):
    global space_status
    global local_bot
    global app
    local_bot = bot
    space_status = update_space_status()

def update_space_status():
    global space_status
    try:
        r = requests.get("http://flipdot.org/spacestatus/status.json")
        if r.status_code == 200:
            return r.json()
        else:
            return space_status
    except:
        return space_status

@interval(INTERVAL)
def update(bot, force=False):
    global space_status
    new_state = update_space_status()
    if new_state is None:
        return
    if space_status is None:
        space_status = new_state
        return
    if new_state['open'] != space_status['open']:
        for c in bot.config.core.channels:
            bot.msg(c,"Space ist {}".format("auf" if space_status['open'] else "zu"))
    space_status = new_state



@sopel.module.commands('tuer','door')
def doorState(bot, trigger):
    global space_status
    if space_status is not None:
        bot.say("Space ist {}".format("auf" if space_status['open'] else "zu"))
    else:
        bot.say("Space status is unbekannt")

@sopel.module.commands('temp','temperatur')
def temperature(bot, trigger):
    global space_status
    msg_setpoint = "Die Heizung ist {}".format(
        "aus" if space_status['temperature_setpoint'] < 6.0
        else "auf {:.2f}°C eingestellt.".format(space_status['temperature_setpoint']))

    msg_temp = "Im Space ist es {:.2f}°C {}. ".format(space_status['temperature_realvalue'],
                          "warm" if space_status['temperature_realvalue'] > 18.0 else "kalt")
    msg = msg_temp + msg_setpoint
    if space_status is not None:
        bot.say(msg)
    else:
        bot.say("Space status is unbekannt")


@sopel.module.commands('users')
def users(bot, trigger):
    global space_status
    if space_status is None:
        bot.say("Space status is unbekannt")
        return
    known_users = space_status.get('known_users', {})
    unknown_user = space_status.get('unknown_users',0)
    if not known_users and (unknown_user == 0):
        bot.say("Es ist niemand im Space")
        return
    if not known_users:
        bot.say("Es sind {} unbekannte im Space".format(space_status['unknown_users']))
        return

    msg = ', '.join(x['nick'] for x in space_status['known_users'])
    if space_status['known_users'] > 0:
        msg = msg + " und {} weitere".format(space_status['unknown_users'])

    msg = msg + " sind im Space"
    bot.say(msg)


@sopel.module.commands('heizen','heatup')
@sopel.module.require_chanmsg(message="Dieser Befehl muss im #flipdot channel eingegeben werden")
@sopel.module.require_privilege(sopel.module.VOICE,"Du darfst das nicht")
def heat(bot, trigger):
    global space_status
    temp = 20
    try:
        if space_status['temperature_setpoint'] > 15:
            bot.say("Die Heizung ist schon an")
            return
        r = requests.get("http://hutschienenpi.fd:8080/CanBus/theemin/SetTargetTemp?temp={:d}".format(temp))
        if r.status_code == 200 and r.content.startswith("OK"):
            bot.say("Stelle die Heizung auf {:.2f}°C".format(temp))
            return
    except Exception as e:
        print(e.message)
        pass

    bot.say("Da ist ein Fehler aufgetreten")


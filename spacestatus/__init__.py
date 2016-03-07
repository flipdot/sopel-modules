# coding=utf8
from __future__ import absolute_import
import sopel
from sopel.module import commands, interval
from sopel import module
import time
import requests
import json
import os
import sys

INTERVAL = 60
MOTION_DETECT_INTERVAL = 3
space_status = None
local_bot = None
last_motion = None

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

@interval(MOTION_DETECT_INTERVAL)
def motion_detect(bot, force=False):
    global local_bot
    global last_motion
    fd = open("/sys/class/gpio/gpio18/value","r")
    tmp = fd.read(1)
    fd.close()
    if tmp  == 0 or tmp == '0' or tmp == "0":
        last_motion = time.strftime("%a %H:%M:%S")


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
            bot.msg(c,"Jmd. hat den Space {}".format("geoeffnet" if new_state['open'] else "geschlossen"))
    space_status = new_state


@sopel.module.commands('bewegungsmelder')
def motion(bot, force=False):
    global last_motion
    if last_motion is None:
        bot.say("Es wurde noch keine Bewegung erkannt")
    else:
        bot.say("Zuletzt bewegte sich etwas im Space am {:s}".format(last_motion))
        

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
    unknown_users = space_status.get('unknown_users',0)
    if not known_users and (unknown_users == 0):
        bot.say("Es ist niemand im Space")
        return
    if not known_users:
        bot.say("Es sind {} unbekannte im Space".format(unknown_users))
        return

    msg = ', '.join(x['nick'] for x in known_users)
    if known_users > 0:
        msg = msg + " und {} weitere".format(unknown_users)

    msg = msg + " sind im Space"
    bot.say(msg)

@sopel.module.commands('status')
def space_status_all(bot, trigger):
    doorState(bot, trigger)
    users(bot, trigger)
    temperature(bot, trigger)

@sopel.module.commands('alarm')
def space_alarm(bot, trigger):
    global space_status
    if space_status is None:
        bot.say("Space status is unbekannt")
        return
    known_users = space_status.get('known_users', {})
    unknown_user = space_status.get('unknown_users',0)
    if space_status['open'] is False and unknown_user is 0 and not known_users:
        bot.say("Niemand zum benachrichtigen im Space")
        return

    r = requests.post("http://hutschienenpi.fd:8080/Hutschiene/RedLight", data={'blink': 'true'})
    if r.status_code is 200:
        bot.say("done")
    else:
        bot.say("Da ist ein Fehler aufgetreten")

@sopel.module.commands('heizen','heatup', 'heizung')
@sopel.module.require_chanmsg(message="Dieser Befehl muss im #flipdot channel eingegeben werden")
@sopel.module.require_privilege(sopel.module.VOICE,"Du darfst das nicht")
def heat(bot, trigger):
    global space_status
    temp = trigger.group(2) or 20
    if temp == "ein":
        temp = "20"
    elif temp == "aus":
        temp = "5"
    try:
        temp = int(temp)
    except ValueError as e:
        bot.say("Bitte eine gerade Zahl in Grad Celsius angeben")
        return
    try:
        if space_status['temperature_setpoint'] is temp:
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


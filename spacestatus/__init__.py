# coding=utf8
from __future__ import absolute_import
import sopel
from sopel.module import commands, interval
from sopel import module
#from socketIO_client import SocketIO

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
    try:
        with open("/sys/class/gpio/export","r+") as f:
            f.write("18")
            f.flush()
    except:
        pass

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
def temp(bot, trigger):
    temperature(bot, '', "lounge");
    #temperature(bot, 'workshop_', "kino");

def temperature(bot, room, room_name):
    global space_status
    no_temp = False
    state = space_status.get(room + 'temperature_setpoint')
    if state is None:
        state = "nicht erreichbar ({})".format(room_name)
        no_temp = True
    elif state < 6.0:
        state = "aus"
    else:
        state = "an"

    msg_setpoint = "Die Heizung ist {}".format(state)
    if no_temp:
        msg = msg_setpoint
    else:
        msg_temp = "{}: Es ist {:.2f}°C {}. ".format(room_name, space_status[room + 'temperature_realvalue'],
                   "warm" if space_status[room + 'temperature_realvalue'] > 18.0 else "kalt")
        msg = msg_temp + msg_setpoint
    if space_status is not None:
        bot.say(msg)
    else:
        bot.say("Space status ist unbekannt")


@sopel.module.commands('users')
def users(bot, trigger):
    global space_status
    if space_status is None:
        bot.say("Space status ist unbekannt")
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
    if len(known_users) > 0:
        msg = msg + " und {} weitere".format(unknown_users)

    msg = msg + " sind im Space"
    bot.say(msg)

@sopel.module.commands('status')
def space_status_all(bot, trigger):
    doorState(bot, trigger)
    users(bot, trigger)
    temp(bot, trigger)

@sopel.module.commands('alarm')
def space_alarm(bot, trigger):
    global space_status
    if space_status is None:
        bot.say("Space status ist unbekannt")
        return
    known_users = space_status.get('known_users', {})
    unknown_user = space_status.get('unknown_users',0)
    if space_status['open'] is False and unknown_user is 0 and not known_users:
        bot.say("Niemand zum benachrichtigen im Space")
        return

    r = requests.post("http://rail.fd:8080/Hutschiene/RedLight", data={'blink': 'true'})
    if r.status_code is 200:
        bot.say("done")
    else:
        bot.say("Da ist ein Fehler aufgetreten")

@sopel.module.commands('heizen','heatup', 'heizung')
@sopel.module.require_chanmsg(message="Dieser Befehl muss im #flipdot channel eingegeben werden")
@sopel.module.require_privilege(sopel.module.VOICE,"Du darfst das nicht")
def heat(bot, trigger):
    global space_status

    can_names = {
    #    "kino" : "thaemin",
        "chill" : "theemin"
    }
    cmd = trigger.group(2) or "20 all"
    cmds = cmd.split(" ")
    
    temp = cmds[0] if len(cmds) > 0 else 20
    room = cmds[1] if len(cmds) > 1 else "all"

    if temp == "ein":
        temp = "20"
    elif temp == "aus":
        temp = "5"
    try:
        temp = int(temp)
    except ValueError as e:
        bot.say("Bitte eine natürliche Zahl in Grad Celsius angeben")
        return

    rooms = []
    if room == "all":
        for k,v in can_names.items():
            rooms.append(k)
    else:
        can_name = can_names[room]
        if not can_name:
            bot.say("{} existiert nicht".format(room))
            return
        rooms.append(room)

    for r in rooms:
        try:
            resp = requests.get("http://rail.fd:8080/CanBus/{:s}/SetTargetTemp?temp={:d}".format(can_names[r], temp))
            if resp.status_code == 200 and resp.text.startswith("OK"):
                bot.say("Stelle Heizung({:s}) auf {:.2f}°C".format(r, temp))
        except Exception as e:
            print(e)
            bot.say("Da ist ein Fehler aufgetreten ({:s})".format(r))

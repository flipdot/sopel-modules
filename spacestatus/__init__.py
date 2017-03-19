# coding=utf8
from __future__ import absolute_import
import sopel
from sopel.module import commands, interval
from sopel import module
# from socketIO_client import SocketIO

import time
import requests
import json
import os
import sys
import sqlite3
import datetime

INTERVAL = 60
MOTION_DETECT_INTERVAL = 3
space_status = None
last_motion = None
CO2 = 300

mampf = "hallo"
datum = "date"
name = "horst"


def setup(bot):
    global space_status
    global app
    space_status = update_space_status()
    try:
        with open("/sys/class/gpio/export", "r+") as f:
            f.write("18")
            f.flush()
    except:
        pass


def update_space_status():
    global space_status

    r = requests.get("http://api.flipdot.org")
    if r.status_code == 200:
        return r.json()
    else:
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
            bot.msg(c, "Der Space wurde {}".format("geoeffnet" if new_state['open'] else "geschlossen"))
    space_status = new_state

@interval(CO2)
def co2(bot, force=False):
    global space_status
    wert = space_status.get("state")["sensors"]["co2"][0]["value"]
    if wert > 1800:
        for c in bot.config.core.channels:
            bot.msg(c, "Wir störben!!1! Mach sofort ein Fenster auf, der CO2 Wert ist zu hoch.")

@interval(MOTION_DETECT_INTERVAL)
def motion_detect(bot, force=False):
    global last_motion
    fd = open("/sys/class/gpio/gpio18/value", "r")
    tmp = fd.read(1)
    fd.close()
    if tmp == 0 or tmp == '0' or tmp == "0":
        last_motion = time.strftime("%a %H:%M:%S")

@sopel.module.commands('bewegungsmelder')
def motion(bot, force=False):
    global last_motion
    if last_motion is None:
        bot.say("Es wurde noch keine Bewegung erkannt")
    else:
        bot.say("Zuletzt bewegte sich etwas im Space am {:s}".format(last_motion))


@sopel.module.commands('tuer', 'door')
def doorState(bot, trigger):
    global space_status
    y = space_status.get("state")["sensors"]["door"][0]["value"]
    if y is not None:
        bot.say("Space ist {}".format("auf" if y == 1 else "zu"))
    else:
        bot.say("Space status is unbekannt")

@sopel.module.commands('temp', 'temperatur')
def temp(bot, trigger):
    temperature(bot, '', "lounge")
    # temperature(bot, 'workshop_', "kino");


def temperature(bot, room, room_name):
    global space_status
    no_temp = False
    for heiz in space_status.get("state")["sensors"]["temperature"]:
        state = heiz['value']
        locate = heiz['location']

        if state < 6.0:
            status = "aus"
        else:
            status = "an"
        msg_setpoint = "Die Heizung ist {}".format(status)


        if state > 18.0:
            zustand = "warm"
        elif state > 10.0:
            zustand = "kalt"
        else:
            zustand = "arschkalt"

        msg_temp = "In {} ist es aktuell {:.2f}°C {}. ".format(locate, state, zustand)
        msg = msg_temp + msg_setpoint

        if space_status is not None:
            bot.say(msg)
        else:
            bot.say("Space status ist unbekannt")


@sopel.module.commands('users')
def users(bot, trigger):
    global space_status
    if space_status is None:
        bot.say("Space status is unbekannt")
        return
    known_users = space_status.get('known_users', {})
    unknown_users = space_status.get('unknown_users', 0)
    names = space_status.get("state")["sensors"]["people_now_present"][0]["names"]
    msg = "Es sind im Space: " + names
    bot.say(msg)

@sopel.module.commands('status')
def space_status_all(bot, trigger):
    if not trigger.is_privmsg:
        status_cnt = bot.db.get_nick_value(trigger.nick, 'status_cnt') or 0
        if status_cnt > 10:
            bot.msg(trigger.nick, "Wir kennen uns doch schon so lange, sprich mich lieber per PM an :o)")
            return

        status_cnt += 1
        bot.db.set_nick_value(trigger.nick, 'status_cnt', status_cnt)

    doorState(bot, trigger)
    users(bot, trigger)
    temp(bot, trigger)


@interval(60 * 60 * 24)
def clear_status_counter(bot, force=False):
    last = bot.db.get_channel_value("#flipdot", "status_cnt") or datetime.datetime.now().month
    if datetime.datetime.now().month == last:
        return

    db = bot.db.connect()
    db.execute('DELETE FROM nick_values WHERE nick_values.key = "status_cnt"')
    db.commit()
    db.close()
    bot.db.set_channel_value("#flipdot", "status_cnt", datetime.datetime.now().month)


@sopel.module.commands('alarm')
def space_alarm(bot, trigger):
    global space_status
    if space_status is None:
        bot.say("Space status ist unbekannt")
        return
    known_users = space_status.get('known_users', {})
    unknown_users = space_status.get('unknown_users', 0)
    names = space_status.get("state")["sensors"]["people_now_present"][0]["names"]
    if space_status.get("state")["sensors"]["door"]["value"][0] is 0 and unknown_users is 0 and not known_users:
        bot.say("Niemand zum benachrichtigen im Space")
        return

    r = requests.post("http://rail.fd:8080/Hutschiene/RedLight", data={'blink': 'true'})
    if r.status_code is 200:
        bot.say("done")
    else:
        bot.say("Da ist ein Fehler aufgetreten")


@sopel.module.commands('heizen', 'heatup', 'heizung')
@sopel.module.require_chanmsg(message="Dieser Befehl muss im #flipdot channel eingegeben werden")
@sopel.module.require_privilege(sopel.module.VOICE, "Du darfst das nicht")
def heat(bot, trigger):
    global space_status

    can_names = {
        #    "kino" : "thaemin",
        "chill": "theemin"
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
        for k, v in can_names.items():
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


@sopel.module.commands('essen')
def futter(bot, trigger):
    global mampf, name, datum
    bot.say(mampf + " gesetzt von: " + name + " am: " + datum)


@sopel.module.commands('kochen')
def kochen(bot, trigger):
    global mampf, name, datum
    if len(trigger.group(2).split(" ")) < 2:
        bot.say("Bitte gib den Kochstatus nach folgendem Schmema ein, [Koch/Ansprechpartner] [Mahlzeit/Essen]")
    else:
        mampf = (trigger.group(2))
        datum = (time.strftime("%d.%m.%Y"))
        name = (trigger.nick)


@sopel.module.commands('futter')
def kochen(bot, trigger):
    api_key = bot.config.spacestatus.forum_key
    res = requests.get(
        'https://forum.flipdot.org/latest.json?api_key=' + api_key + '&api_username=flipbot',
        headers={"Accept": "application/json"})
    topics = res.json()

    cooking_category_id = 19  # "Kochen & Essen"

    cooking_topic = None
    for t in topics['topic_list']['topics']:
        if t['category_id'] == cooking_category_id:
            cooking_topic = t
            break

    cooking_topic_name = cooking_topic['title']
    bot.say("Futter: " + cooking_topic_name)

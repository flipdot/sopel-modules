# coding=utf8
from __future__ import absolute_import
import sopel
from sopel.module import commands, interval
from threading import Thread
import paho.mqtt.client as mqtt

from .webserver import run_server

from sopel import module
# from socketIO_client import SocketIO

import logging
import time
import requests
import json
import os
import sys
import sqlite3
import datetime

INTERVAL = 60
space_status = None
last_motion = None
mqtt_client = None

logger = logging.getLogger(__name__)

CO2 = 3600

def setup(bot):
    global space_status
    global app
    global mqtt_client

    webserver_thread = Thread(target=run_server, args=(bot,))
    webserver_thread.daemon = True
    webserver_thread.start()

    mqtt_client = mqtt.Client()
    mqtt_client.connect('power-pi.fd')
    mqtt_client.loop_start()

    space_status = update_space_status()


def update_space_status():
    global space_status

    try:
        r = requests.get('https://api.flipdot.org', timeout=5)
        if r.status_code == 200 and r.json().get('api', '0') == '0.13':
            return r.json()
        else:
            return space_status
    except:
        logger.exception('Failed to fetch spaceapi')
        return space_status

def get_sensor_val(name, field='value'):
    global space_status
    try:
        return space_status['state']['sensors'][name][0][field]
    except:
        return None


def get_sensor_location(type, location, state=None):
    global space_status
    if state is None:
        state = space_status

    locations = state['state']['sensors'][type]
    for obj in locations:
        if obj['location'] == location:
            return obj
    return None

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
            bot.msg(c, 'Der Space wurde {}'.format('hochgefahren' if new_state['open'] else 'heruntergefahren'))

    try:
        new_locked = get_sensor_location('door', 'locked', new_state)
        old_locked = get_sensor_location('door', 'locked')
        if not new_locked:
            return
        if old_locked['value'] != new_locked['value']:
            for c in bot.config.core.channels:
                bot.msg(c, 'Der Space wurde {}'.format('abgeschlossen' if new_locked['value'] else 'aufgeschlossen'))
    except KeyError:
        print('missing \'door\' sensor in fd api')
    finally:
        space_status = new_state

@interval(CO2)
def co2(bot, force=False):
    wert = get_sensor_val('co2')
    if wert and wert > 2400:
        for c in bot.config.core.channels:
            bot.msg(c, 'Wir störben!!1! Mach sofort ein Fenster auf, der CO2 Wert ist zu hoch.')


@sopel.module.commands('tuer', 'door')

def doorState(bot, trigger):
    global space_status
    y = space_status.get('state').get('open')
    if y is not None:
        bot.say('Space ist {}'.format('auf' if y else 'zu'))
    else:
        bot.say('Space status is unbekannt')


@sopel.module.commands('temp', 'temperatur')

def temp(bot, trigger):
    temperature(bot, '', 'lounge')
    # temperature(bot, 'workshop_', 'kino');


def temperature(bot, room, room_name):
    global space_status

    if space_status is None:
        bot.say('Space status ist unbekannt')
        return

    for heiz in space_status.get('state')['sensors']['temperature']:
        state = heiz['value']
        locate = heiz['location']

        if state > 18.0:
            zustand = 'warm'
        elif state > 10.0:
            zustand = 'kalt'
        else:
            zustand = 'arschkalt'

        bot.say('In {} ist es aktuell {:.2f}°C {}. '.format(locate, state, zustand))



@sopel.module.commands('users')
def users(bot, trigger):
    global space_status
    if space_status is None:
        bot.say('Space status is unbekannt')
        return

    names = get_sensor_val('people_now_present', 'names')
    user_count = get_sensor_val('people_now_present')

    if not user_count or user_count is 0:
        bot.say('Es ist niemand im Space')
        return

    names = names.split(',')
    user_count -= len(names)
    known = ', '.join(x for x in names)

    if user_count is 0:
        bot.say('Es sind im Space: {}'.format(known))
    elif len(names) is 0:
        bot.say('Es sind {} unbekannte im Space'.format(user_count))
    else:
        bot.say('Es sind {} unbekannte und {} im Space'.format(user_count, known))


@sopel.module.commands('status')
def space_status_all(bot, trigger):
    doorState(bot, trigger)
    users(bot, trigger)
    temp(bot, trigger)


@interval(60 * 60 * 24)
def clear_status_counter(bot, force=False):
    last = bot.db.get_channel_value('#flipdot', 'status_cnt') or datetime.datetime.now().month
    if datetime.datetime.now().month == last:
        return

    db = bot.db.connect()
    db.execute('DELETE FROM nick_values WHERE nick_values.key = \'status_cnt\'')
    db.commit()
    db.close()
    bot.db.set_channel_value('#flipdot', 'status_cnt', datetime.datetime.now().month)



@sopel.module.commands('heizen', 'heatup', 'heizung')
@sopel.module.require_chanmsg(message='Dieser Befehl muss im #flipdot channel eingegeben werden')
@sopel.module.require_privilege(sopel.module.VOICE, 'Du darfst das nicht')
def heat(bot, trigger):
    global space_status

    bot.say('Kaputt')

    mqtt_names = {
        'raum4': 'f376db',
        'lounge': 'f391d8',
        'm-shop': '4c857f'
    }
    cmd = trigger.group(2) or '20 all'
    cmds = cmd.split(' ')

    temp = cmds[0] if len(cmds) > 0 else 20
    room = cmds[1] if len(cmds) > 1 else 'all'

    if temp == 'ein':
        temp = '20'
    elif temp == 'aus':
        temp = '5'
    try:
        temp = int(temp)
    except ValueError as e:
        bot.say('Bitte eine natürliche Zahl in Grad Celsius angeben')
        return

    rooms = []
    if room == 'all':
        for k, v in mqtt_names.items():
            rooms.append(k)
    else:
        mqtt_name = mqtt_names[room]
        if not mqtt_name:
            bot.say('{} existiert nicht'.format(room))
            return
        rooms.append(room)

    for r in rooms:
        try:
            mqtt_client.publish('sensors/heater/{}/fenster/setpoint'.format(mqtt_names[r]), temp)
            bot.say('Stelle Heizung({:s}) auf {:.2f}°C'.format(r, temp))
        except Exception as e:
            print(e)
            bot.say('Da ist ein Fehler aufgetreten ({:s})'.format(r))


@sopel.module.commands('essen')
def essen(bot, trigger):
    futter = bot.db.get_channel_value('#flipdot', 'hapahapa') or 'nix'
    bot.say(futter)


@sopel.module.commands('kochen')
def kochen(bot, trigger):
    if trigger.group(2) is None or len(trigger.group(2).split(' ')) < 2:
        bot.say('Bitte gib den Kochstatus nach folgendem Schmema ein, [Koch/Ansprechpartner] [Mahlzeit/Essen]')
    else:
        x = trigger.group(2).split(' ')
        msg = '{} kocht {}'.format(x[0], x[1])
        bot.db.set_channel_value('#flipdot', 'hapahapa', msg)
        bot.say('done')


@sopel.module.commands('futter')
def futter(bot, trigger):
    api_key = bot.config.spacestatus.forum_key
    res = requests.get(
        'https://forum.flipdot.org/latest.json?api_key=' + api_key + '&api_username=flipbot',
        headers={'Accept': 'application/json'})
    topics = res.json()

    cooking_category_id = 19  # 'Kochen & Essen'

    cooking_topic = None
    for t in topics['topic_list']['topics']:
        if t['category_id'] == cooking_category_id:
            cooking_topic = t
            break

    cooking_topic_name = cooking_topic['title']
    bot.say('Futter: ' + cooking_topic_name)

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
    r = requests.get("http://flipdot.org/spacestatus/status.json")
    if r.status_code != 200:
        return space_status
    else:
        space_status = r.json()

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
            bot.msg(c,"Space ist %s" % ("auf" if space_status['open'] else "zu"))
    space_status = new_state



@sopel.module.commands('tuer','door')
def doorState(bot, trigger):
    global space_status
    if space_status is not None:
        bot.say("Space ist %s" % ("auf" if space_status['open'] else "zu"))
    else:
        bot.say("Space status is unbekannt")

@sopel.module.commands('temp','temperatur')
def temperature(bot, trigger):
    global space_status
    if space_status is not None:
        bot.say("Im Space ist es %.2f°C %s" % (space_status['temperature_realvalue'],
                                               "warm" if space_status['temperature_realvalue'] > 18.0 else "kalt"))
    else:
        bot.say("Space status is unbekannt")


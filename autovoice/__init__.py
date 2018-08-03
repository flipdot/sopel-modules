# Gives voice to everybody who is on the channel longer than up to two times
# INTERVAL seconds.
#
# See here for more information:
# http://docs.dal.net/docs/modes.html#2.22

import sopel
from time import sleep
from sopel.module import interval, OP, VOICE

INTERVAL = 300
CHANNEL = '#flipdot'
last_privs = None


@sopel.module.interval(INTERVAL)
def auto_voice(bot, force=False):
    global last_privs
    if not last_privs:
        last_privs = bot.privileges
    for nick, priv in bot.privileges[CHANNEL].items():
        if nick in last_privs[CHANNEL] and bot.privileges[CHANNEL][nick] < VOICE:
            bot.write(['MODE', CHANNEL, '+v', nick])
    last_privs = bot.privileges

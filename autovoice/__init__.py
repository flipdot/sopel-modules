import sopel
from time import sleep
from sopel.module import interval, OP, VOICE
import threading

INTERVAL = 300
CHANNEL = '#flipdot'

auto_voice_threads = {}


def set_voice(bot, nick):
    global auto_voice_threads
    bot.write(['MODE', CHANNEL, '+v', nick])
    if nick in auto_voice_threads.keys():
        auto_voice_threads.pop(nick)



@sopel.module.rule('.*')
@sopel.module.event("JOIN")
def auto_voice_join(bot, trigger):
    global auto_voice_threads
    if trigger.host.startswith("gateway/shell/matrix.org"):
        set_voice(bot, trigger.nick)
    else:
        auto_voice_threads[trigger.nick] = threading.Timer(INTERVAL, set_voice, [bot, trigger.nick])
        auto_voice_threads[trigger.nick].start()


@sopel.module.rule('.*')
@sopel.module.event("PART", "QUIT")
def auto_voice_quit(bot, trigger):
    global auto_voice_threads
    if trigger.nick in auto_voice_threads.keys():
        auto_voice_threads[trigger.nick].cancel()
        auto_voice_threads.pop(trigger.nick)



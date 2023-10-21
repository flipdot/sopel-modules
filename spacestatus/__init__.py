# coding=utf8
import sopel
from sopel.module import commands, interval
from sopel import module

import logging
import requests
import json
import datetime

INTERVAL = 60
space_status = None

logger = logging.getLogger(__name__)


def setup(bot):
    global space_status

    space_status = update_space_status()


def update_space_status() -> Mapping:
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

def get_sensor_val(name: str, field='value') -> Optional[float]:
    global space_status
    try:
        return space_status['state']['sensors'][name][0][field]
    except:
        return None


def get_sensor_location(sensor_type: str, location: str, state=None) -> Optional[Mapping]:
    global space_status
    if state is None:
        state = space_status

    locations = state['state']['sensors'][sensor_type]
    for obj in locations:
        if obj['location'] == location:
            return obj
    return None

@interval(INTERVAL)
def update(bot, force=False) -> None:
    global space_status

    new_state = update_space_status()
    if new_state is None:
        return
    if space_status is None:
        space_status = new_state
        return

    if new_state['open'] != space_status['open']:

        new_power_status = ('🔌', 'hochgefahren') if new_state['open'] else ('⏸️', 'heruntergefahren')

        for c in bot.config.core.channels:
            bot.msg(c, f'{new_power_status[0]} Der Space wurde {new_power_status[1]}.')

    try:
        new_locked = get_sensor_location('door', 'locked', new_state)
        old_locked = get_sensor_location('door', 'locked')
        if not new_locked:
            return
        if old_locked['value'] != new_locked['value']:

            new_lock_state = ('🔐', 'abgeschlossen') if new_locked['value'] else ('🔓', 'aufgeschlossen')

            for c in bot.config.core.channels:
                bot.msg(c, f'{new_lock_state[0]} Der Space wurde {new_lock_state[1]}.')

    except KeyError:
        print('missing \'door\' sensor in fd api')
    finally:
        space_status = new_state


@sopel.module.commands('tuer', 'door')
def doorState(bot, trigger) -> None:
    global space_status
    y = space_status.get('state').get('open')
    if y is not None:
        status = 'auf' if y else 'zu'
        bot.say(f'Space ist {status}')
    else:
        bot.say('Space-Status is unbekannt :(')


@sopel.module.commands('users')
def users(bot, trigger) -> None:
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
        bot.say(f'Es sind im Space: {known}')
    elif len(names) is 0:
        bot.say(f'Es sind {user_count} unbekannte im Space')
    else:
        bot.say(f'Es sind {user_count} unbekannte und {known} im Space')


@sopel.module.commands('status')
def space_status_all(bot, trigger) -> None:
    doorState(bot, trigger)
    users(bot, trigger)


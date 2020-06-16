"""Loads stats on Covid-19 for the city of Kassel using ArcGIS' API"""
import json
import locale
import re
import requests

import pandas as pd

from bs4 import BeautifulSoup
from datetime import datetime
from sopel import module
from sopel.config.types import StaticSection, ValidatedAttribute

# Colored prefix
#   \x03AA,BB
#   AA = foreground color
#   BB = background color
#   ,BB can be omitted
#
#   For more information
#   https://github.com/myano/jenni/wiki/IRC-String-Formatting
#   http://www.mirc.co.uk/colors.html
COLOR_COVID  = '\x0304' # red
COLOR_BOLD   = '\x02'
COLOR_RESET  = '\x0F'
COLOR_PREFIX = '[%spsa%s]' % (COLOR_COVID, COLOR_RESET)

PREFIX = '[psa]'
KEY_TIME = 'Aktualisierung'

TS_FORMATS = [
    'Stand: %d. %B %Y',
    'Stand: %d. %B %Y; %H Uhr',
    'Stand: %d. %B %Y; %H.%M Uhr',
]

LOC_LUT = {
    'Stadt Kassel': 'Kassel Stadt',
    'Landkreis Kassel': 'Kassel Land',
}

REPR_LUT = {
    'Gemeldete Fälle insgesamt': 'insgesamt',
    'Genesene': 'genesen',
    'Aktuell Infizierte': 'infiziert',
    'Todesfälle': 'tot',
}


class CovidSection(StaticSection):
    announce_channel = ValidatedAttribute('announce_channel', default='#flipdot-covid')
    url = ValidatedAttribute('url', default='https://kassel.de/coronavirus')


def update_check(ts_old, update_raw):
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    soup = BeautifulSoup(update_raw, 'html.parser')
    ts_str = soup.find('h1', 'SP-Headline--paragraph').text
    ts_new = None
    for ts_format in TS_FORMATS:
        try:
            ts_new = datetime.strptime(ts_str, ts_format).strftime('%s')
            break
        except:
            pass
    if ts_new is None:
        raise SyntaxError(f"No time format could parse the raw string '{ts_str}'.")
    else:
        update_required = False
    if int(ts_old) < int(ts_new):
        update_required = True
    data_cases = pd.read_html(str(soup.table))[0].set_index('Vorkommen')
    return update_required, ts_new, data_cases


def update_repr(prefix, update_data_pre, add_prefix=False):
    first_line = True
    ret = ''
    if add_prefix:
        ret += f"{prefix} "
    for loc in LOC_LUT.keys():
        if not first_line:
            first_ljust_len = len(LOC_LUT[list(LOC_LUT.keys())[0]]) - len(prefix)
            ret += '\n'.ljust(first_ljust_len)
        first_line = False
        ret += f"{LOC_LUT[loc]}: "
        first_field = True
        for k, v in REPR_LUT.items():
            field = update_data_pre.loc[loc][k]
            try:
                if int(field) == 0:
                    continue
            except:
                pass
            if not first_field:
                ret += ', '
            first_field = False
            ret += f"{field} {v}"
    return ret


@module.interval(5 * 60)
def covid_update(bot, dest=None, update_forced=False):
    print(f"{PREFIX} Checking COVID-19 data...")
    ts_old, cases = cache_load(bot)
    req = requests.get(bot.config.covid.url)
    if req.status_code != 200:
        raise ConnectionError("Could not download covid data.")
    update_raw = req.text
    update_required, ts_old, update_data = update_check(ts_old, update_raw)
    if not update_required and not update_forced:
        print(f"{PREFIX} No update...")
        return
    msg = update_repr(PREFIX, update_data)
    if dest is None:
        dest = bot.config.covid.announce_channel
    for line in f"{COLOR_PREFIX} {msg}".split('\n'):
        bot.say(line, dest)
    cache_save(bot, ts_old, update_data)
    print(f"{PREFIX} Updates cached...")


@module.commands('covidclear')
def covid_clear(bot, trigger):
    print(f"{PREFIX} Clearing COVID-19 cache...")
    chan = bot.config.covid.announce_channel
    bot.db.set_channel_value(chan, 'ts_old', 0)
    bot.db.set_channel_value(chan, 'cases', None)


@module.commands('covid')
def covid_print(bot, trigger):
    covid_update(bot)#, dest=trigger.nick, update_forced=True)


def setup(bot):
    bot.config.define_section('covid', CovidSection)


def cache_load(bot):
    chan = bot.config.covid.announce_channel
    ts_old = bot.db.get_channel_value(chan, 'ts_old') or 0
    cases_bot = bot.db.get_channel_value(chan, 'cases')
    if isinstance(cases_bot, pd.DataFrame):
        cases_str = pd.read_json(cases_bot)
    else:
        cases_str = None
    if isinstance(cases_str, str):
        cases = json.loads(cases_str)
    else:
        cases = cases_str
    return ts_old, cases


def cache_save(bot, ts_old, update_data):
    chan = bot.config.covid.announce_channel
    bot.db.set_channel_value(chan, 'ts_old', ts_old)
    bot.db.set_channel_value(chan, 'cases', update_data.to_json())

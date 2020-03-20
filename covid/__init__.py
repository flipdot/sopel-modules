"""Loads stats on Covid-19 for the city of Kassel using ArcGIS' API"""
import json
import locale
import re
import requests

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


class CovidSection(StaticSection):
    announce_channel = ValidatedAttribute('announce_channel', default='#flipdot-covid')
    url = ValidatedAttribute('url', default='https://kassel.de/coronavirus')
    cases_default = ValidatedAttribute('cases_default', default={"SK Kassel": {"Aktualisierung": 0, "Fallzahlen": 0, "Death": 0}, "LK Kassel": {"Aktualisierung": 0, "Fallzahlen": 0, "Death": 0}})


def update_check(cases, update_raw):
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    soup = BeautifulSoup(update_raw, 'html.parser')
    ts_str = soup.find('h1', 'SP-Headline--paragraph').text
    ts_new = datetime.strptime(ts_str, 'Stand: %d. %B %Y; %H Uhr').strftime('%s')
    k = [e.text for e in soup.table.find_all('strong')]
    l = len(k)
    v_raw = soup.table.find_all('td')[l:]
    s = len(v_raw) // l
    v_pre = {v_raw[i * l].text: v_raw[i * l + 1:(i + 1) * l] for i in range(s)}
    ts_old = cases[list(cases.keys())[0]].get(KEY_TIME)
    if int(ts_old) < int(ts_new):
        update_required = True
    else:
        update_required = False
    return update_required, {
        'SK Kassel': {
            'Aktualisierung': ts_new,
            'Fallzahlen': v_pre['Stadt Kassel'][0].text,
            'Fallzahlen_rel': v_pre['Stadt Kassel'][1].text.replace(' ', ''),
            'Death': v_pre['Stadt Kassel'][2] if len(v_pre['Stadt Kassel']) > 2 else 0,
            # 'Death_rel': FIXME
        },
        'LK Kassel': {
            'Aktualisierung': ts_new,
            'Fallzahlen': v_pre['Landkreis Kassel'][0].text,
            'Fallzahlen_rel': v_pre['Landkreis Kassel'][1].text.replace(' ', ''),
            'Death': v_pre['Landkreis Kassel'][2] if len(v_pre['Landkreis Kassel']) > 2 else 0,
            # 'Death_rel': FIXME
        },
    }


def update_repr(prefix, update_data_pre, add_prefix=False):
    first_line = True
    ret = ''
    if add_prefix:
        ret += f'{prefix} '
    for location, data in update_data_pre.items():
        if not first_line:
            ret += '\n'.ljust(len(prefix) + 3)
        m = re.search(r'^(SK|LK)\s([A-Za-z ]+)$', location)
        if m is not None:
            district, city = m.groups()
        else:
            district, city = None, location
        first_line = False
        ret += f'{city} '
        if district is not None:
            if district == 'SK':
                ret += 'Stadt'
            elif district == 'LK':
                ret += 'Land'
            ret += ': '
        ret += f"{data['Fallzahlen']} "
        cases_rel = data.get('Fallzahlen_rel')
        if cases_rel:
            ret += f"({cases_rel}) "
        ret += "infiziert"
        death = data['Death']
        if death > 0:
            ret += f", {data['Death']} tot"
        # death_rel = data['Death_rel'] # FIXME
    return ret


@module.interval(5 * 60)
def covid_update(bot, dest=None, update_forced=False):
    print(f"{PREFIX} Checking COVID-19 data...")
    cases = cache_load(bot)
    req = requests.get(bot.config.covid.url)
    if req.status_code != 200:
        raise ConnectionError("Could not download covid data.")
    update_raw = req.text
    update_required, update_data = update_check(cases, update_raw)
    if not update_required and not update_forced:
        print(f"{PREFIX} No update...")
        return
    msg = update_repr(PREFIX, update_data)
    if dest is None:
        dest = bot.config.covid.announce_channel
    for line in f"{COLOR_PREFIX} {msg}".split('\n'):
        bot.say(line, dest)
    cache_save(bot, update_data)
    print(f"{PREFIX} Updates cached...")


@module.commands('covidclear')
def covid_clear(bot, trigger):
    print(f"{PREFIX} Clearing COVID-19 cache...")
    chan = bot.config.covid.announce_channel
    bot.db.set_channel_value(chan, 'cases', bot.config.covid.cases_default)


@module.commands('covid')
def covid_print(bot, trigger):
    covid_update(bot)#, dest=trigger.nick, update_forced=True)


def setup(bot):
    bot.config.define_section('covid', CovidSection)


def cache_load(bot):
    chan = bot.config.covid.announce_channel
    cases_str = bot.db.get_channel_value(chan, 'cases') or bot.config.covid.cases_default
    if isinstance(cases_str, str):
        cases = json.loads(cases_str)
    else:
        cases = cases_str
    return cases


def cache_save(bot, update_data):
    chan = bot.config.covid.announce_channel
    bot.db.set_channel_value(chan, 'cases', update_data)

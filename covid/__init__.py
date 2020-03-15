"""Loads stats on Covid-19 for the city of Kassel using ArcGIS' API"""
import json
import re
import requests

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
    url = ValidatedAttribute('url', default='https://services7.arcgis.com/mOBPykOjAyBO2ZKk/arcgis/rest/services/Kreisgrenzen_2018_mit_Einwohnerzahl/FeatureServer/0/query?f=json&where=1%3D1&returnGeometry=false&spatialRel=esriSpatialRelIntersects&geometry=%7B%22xmin%22%3A1022582.0406873999%2C%22ymin%22%3A6640566.110841996%2C%22xmax%22%3A1071425.301761622%2C%22ymax%22%3A6707907.132761228%2C%22spatialReference%22%3A%7B%22wkid%22%3A102100%2C%22latestWkid%22%3A3857%7D%7D&geometryType=esriGeometryEnvelope&inSR=102100&outFields=*&orderByFields=Fallzahlen%20desc&outSR=102100&resultOffset=0&resultRecordCount=1000')
    cases_default = ValidatedAttribute('cases_default', default={"SK Kassel": {"Aktualisierung": 0, "Fallzahlen": 0, "Death": 0}, "LK Kassel": {"Aktualisierung": 0, "Fallzahlen": 0, "Death": 0}})


def update_check(cases, update_raw):
    update_required = False
    update_data = {}
    for u in update_raw:
        attr = u.get('attributes')
        district = attr.get('RKI_Kreis')
        if district in cases.keys():
            if attr.get(KEY_TIME) <= cases[district].get(KEY_TIME):
                continue
            update_required = True
            update_data[district] = {}
            # Store only requested data
            for k, v in attr.items():
                if k not in cases[district].keys():
                    continue
                update_data[district][k] = v
    return update_required, update_data


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
        ret += f"{data['Fallzahlen']} infiziert"
        death = data['Death']
        if death > 0:
            ret += f", {data['Death']} tot"
    return ret


@module.interval(5 * 60)
def covid_update(bot, dest=None, update_forced=False):
    print(f"{PREFIX} Checking COVID-19 data...")
    cases = cache_load(bot)
    req = requests.get(bot.config.covid.url)
    if req.status_code != 200:
        raise ConnectionError("Could not download covid data.")
    update_raw = req.json()['features']
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

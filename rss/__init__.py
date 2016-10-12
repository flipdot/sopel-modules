#"""RSS module for sopel
#
#Print information on changes of an RSS feed by polling and parsing it.
#"""

import re
import requests
import time

from sopel import module
from sopel.module import interval
from sopel.config.types import StaticSection, ValidatedAttribute

try:
    import xml.etree.cElementTree as et
except ImportError:
    print("cElementTree not found. Using slower Python implementation 'ElementTree' instead.")
    import xml.etree.ElementTree as et


# Time in seconds, that the bot reloads network metrics
INTERVAL_UPDATE = 60

# Colored prefix
#   \x03AA,BB
#   AA = foreground color
#   BB = background color
#   ,BB can be omitted
#
#   For more information
#   https://github.com/myano/jenni/wiki/IRC-String-Formatting
#   http://www.mirc.co.uk/colors.html
COLOR_NETWORK = '\x0309' # light green
COLOR_BOLD    = '\x02'
COLOR_RESET   = '\x0F'
COLOR_PREFIX  = '[%sblg%s]' % (COLOR_NETWORK, COLOR_RESET)


class RssSection(StaticSection):
    rss_url = ValidatedAttribute('rss_url', default='https://flipdot.org/blog/index.php?/feeds/index.rss2')
    announce_channel = ValidatedAttribute('announce_channel', default='#flipdot')


def setup(bot):
    bot.config.define_section('rss', RssSection)


###@interval(INTERVAL_UPDATE)
def check_recent_changes(bot, force=False):
    """Download recent changes xml file and print on diff with local cache"""
    announce_channel = bot.config.rss.announce_channel

    r = requests.get(bot.config.rss.rss_url)
    if r.status_code != 200:
        bot.say("{} Could not download recent entries".format(COLOR_PREFIX), announce_channel)
        return

    rss = r.text.encode('utf-8')
    timestamp = bot.db.get_channel_value(bot.config.rss.announce_channel, 'rss_timestamp') or 0
    items = parse_xml(rss)

    for item in items:
        if item.date < timestamp:
            continue
        bot.say("{} {}{}{} blogged by {}:".format(COLOR_PREFIX,
                 COLOR_BOLD,
                 item['title'],
                 COLOR_RESET,
                 item['author']), announce_channel)
        bot.say("      {}".format(item['url']), announce_channel)

    #timestamp = bot.db.set_channel_value(bot.config.rss.announce_channel, 'rss_timestamp', time.time())

# Parses MoinMoin's RSS XML structure and gives back a list of dicts with the
# following elements:
#   author
#   date
#   title
#   url
def parse_xml(xml_string):
    tree = et.fromstring(xml_string)
    items = []

    print("QWER")
    for item in tree.findall("item"):
        print("ASDF")
        author = item.find("author").text
        date = item.find("pubDate").text
        title = item.find("title").text
        url = item.find("link").text

        #author = re.sub(r"Self:(.+)", r"\1", author)

        items.append({"author":author,
                      "date":date,
                      "title":title,
                      "url":url})

    return items

with open('/tmp/time.time/index.rss', 'r') as xml_file:
    xml_content = xml_file.read()
print(parse_xml(xml_content))
import pdb; pdb.set_trace()  # XXX BREAKPOINT


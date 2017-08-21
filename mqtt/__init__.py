import json
from threading import Thread

import sopel
import paho.mqtt.client as mqtt

MQTT_HOST = "rail.fd"
MQTT_TOPIC = "actors/all/flipbot_send"

#   For more information
#   https://github.com/myano/jenni/wiki/IRC-String-Formatting
COLOR_IOT = "\x0307"  # orange
COLOR_RESET = "\x0F"
COLOR_PREFIX = "[{}iot{}]".format(COLOR_IOT, COLOR_RESET)

bot = None


def on_mqtt_connect(client, userdata, flags, result):
    client.subscribe(MQTT_TOPIC)


def on_mqtt_message(client, userdata, msg):
    msg_obj = json.loads(msg.payload.decode("utf-8"))
    msg = "{} {}".format(COLOR_PREFIX, msg_obj["content"])

    for c in bot.config.core.channels:
        bot.msg(c, msg)


def mqtt_main():
    client = mqtt.Client()
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    client.connect(MQTT_HOST)
    client.loop_forever()


def setup(b):
    global bot
    bot = b

    mqtt_thread = Thread(target=mqtt_main)
    mqtt_thread.daemon = True
    mqtt_thread.start()

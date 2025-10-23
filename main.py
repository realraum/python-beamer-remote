# mqtt client (paho)
from time import sleep

from paho.mqtt.client import Client
import socket
import json
import subprocess

COMMANDS = {
    # input
    "inputHdmi": [0xcd, 0x13],
    "inputPc": [0xd0, 0x13],
    "inputComponent1": [0xd1, 0x13],
    "inputComponent2": [0xd2, 0x13],
    "inputSVideo": [0xcf, 0x13],
    "inputVideo": [0xce, 0x13],

    # volume
    "volumeUp": [0xfa, 0x13],
    "volumeDown": [0xfb, 0x13],
    "volumeMute": [0xfc, 0x13],
    "volumeUnmute": [0xfd, 0x13],

    # power
    "powerOn": [0x04, 0x00],
    "powerOff": [0x05, 0x00],

    # menu
    "menuToggle": [0x1d, 0x14],
    "menuUp": [0x1e, 0x14],
    "menuDown": [0x1f, 0x14],
    "menuLeft": [0x20, 0x14],
    "menuRight": [0x21, 0x14],
    "menuOk": [0x23, 0x14],

    # picture
    "pictureMute": [0xee, 0x13],
    "pictureUnmute": [0xef, 0x13],
    "pictureFreeze": [0xf0, 0x13],
    "pictureUnfreeze": [0xf1, 0x13],
    "pictureContrastUp": [0xf6, 0x13],
    "pictureContrastDown": [0xf7, 0x13],
    "pictureBrightnessUp": [0xf5, 0x13],
    "pictureBrightnessDown": [0xf4, 0x13]
}

# constants

MQTT_SERVER="mqtt.realraum.at"
MQTT_PORT=1883
MQTT_WILL_TOPIC="r3beamerremote/status"
MQTT_WILL_PAYLOAD="offline"
MQTT_WILL_RETAIN=True
MQTT_WILL_QOS=1

BEAMER_IP_ADDRESS="192.168.25.11"
BEAMER_PORT=41794

def get_git_hash():
    try:
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode()
        git_dirty = subprocess.check_output(['git', 'diff', '--quiet', 'HEAD', '||', 'echo', 'dirty']).strip().decode()
        return git_hash, git_dirty
    except Exception as e:
        return "unknown", "unknown"

def publish_home_assistant_discovery(client: Client):
    """
    std::string topic = fmt::format("homeassistant/button/r3beamerremote_{}/config", commandName);
    std::string unique_id = fmt::format("r3beamerremote_{}_{}", commandName, WiFi.macAddress().c_str());
    std::string command_topic = "r3beamerremote/command";

    auto obj = doc.to<JsonObject>();

    obj["name"] = commandName;
    obj["icon"] = "mdi:remote";
    obj["command_topic"] = command_topic;
    obj["unique_id"] = unique_id;
    obj["payload_press"] = commandName;

    // availability
    obj["availability_topic"] = MQTT_WILL_TOPIC;
    obj["payload_available"] = "online";
    obj["payload_not_available"] = "offline";

    obj["device"]["identifiers"] = WiFi.macAddress();
    obj["device"]["name"] = HOSTNAME;
    obj["device"]["model"] = "ESP32";
    obj["device"]["manufacturer"] = "realraum";

    // also include the software version from git
    obj["device"]["sw_version"] = std::string(GIT_HASH) + (std::string(GIT_DIRTY) == "dirty" ? "-dirty" : "");
    """

    hostname = socket.gethostname()
    mac_address = ':'.join(['{:02x}'.format((socket.gethostbyname(hostname).encode()[i]) & 0xff) for i in range(6)])

    for command_name in COMMANDS.keys():
        topic = f"homeassistant/button/r3beamerremote_{command_name}/config"
        unique_id = f"r3beamerremote_{command_name}_{mac_address}"
        command_topic = "r3beamerremote/command"

        payload = {
            "name": command_name,
            "icon": "mdi:remote",
            "command_topic": command_topic,
            "unique_id": unique_id,
            "payload_press": command_name,
            "availability_topic": MQTT_WILL_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": {
                "identifiers": mac_address,
                "name": hostname,
                "model": "Python MQTT Beamer Remote",
                "manufacturer": "realraum",
                "sw_version": "{}-{}".format(*get_git_hash())
            }
        }

        print(f"Publishing Home Assistant discovery for {command_name} to topic {topic}")
        print(json.dumps(payload, indent=2))

        client.publish(topic, json.dumps(payload), qos=1, retain=True)


def on_connect(client: Client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("r3beamerremote/command")

    # publish online status
    client.publish("r3beamerremote/status", "online", qos=1, retain=True)
    publish_home_assistant_discovery(client)


def on_message(client: Client, userdata, msg):
    # print as [topic]: payload
    print(f"[{msg.topic}]: {msg.payload.decode()}")


def main():
    mqtt_client = Client()
    mqtt_client.will_set(MQTT_WILL_TOPIC, MQTT_WILL_PAYLOAD, MQTT_WILL_QOS, MQTT_WILL_RETAIN)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTT_SERVER, MQTT_PORT, 60)

    mqtt_client.loop_start()

    while True:
        try:
            sleep(1)
            print("Foo")
        except KeyboardInterrupt:
            mqtt_client.loop_stop()
            print("Exiting...")
            break

if __name__ == "__main__":
    main()
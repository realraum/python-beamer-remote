import paho.mqtt.client as mqtt
import socket
import json
import subprocess
from flask import Flask, jsonify
from os import environ

app = Flask(__name__, static_url_path='', static_folder='www')

last_power_command: bool | None = None

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

MQTT_SERVER = "mqtt.realraum.at"
MQTT_PORT = 1883
MQTT_WILL_TOPIC = "r3beamerremote/status"
MQTT_WILL_PAYLOAD = "offline"
MQTT_WILL_RETAIN = True
MQTT_WILL_QOS = 1

BEAMER_IP_ADDRESS = environ.get("BEAMER_IP_ADDRESS", "192.168.35.11")
BEAMER_PORT = environ.get("BEAMER_PORT", 41794)

WEB_SERVER_HOST = environ.get("WEB_SERVER_HOST", "0.0.0.0")
WEB_SERVER_PORT = environ.get("WEB_SERVER_PORT", 5420)


def get_git_dirty():
    try:
        git_status = subprocess.check_output(['git', 'status', '--porcelain']).strip().decode()
        git_dirty = "dirty" if git_status != "" else "clean"
        return git_dirty
    except Exception as e:
        print(f"Could not get git dirty state: {e}")
        return "unknown"


def get_git_hash():
    try:
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode()
        return git_hash
    except Exception as e:
        print(f"Could not get git hash: {e}")
        return "unknown"


GIT_HASH, GIT_DIRTY = get_git_hash(), get_git_dirty()


def publish_home_assistant_discovery(client: mqtt.Client):
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
                "sw_version": "{}-{}".format(GIT_HASH, "dirty" if GIT_DIRTY != "" else "clean")
            }
        }

        print(f"Publishing Home Assistant discovery for {command_name} to topic {topic}")

        client.publish(topic, json.dumps(payload), qos=1, retain=True)


def handle_command(command: str) -> bool:
    global last_power_command

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        return False

    base_payload = [0x05, 0x00, 0x06, 0x00, 0x00, 0x03, 0x00]

    command_payload = COMMANDS[command]

    full_payload = base_payload + command_payload

    print(f"Sending command {command} with payload {full_payload} to beamer at {BEAMER_IP_ADDRESS}:{BEAMER_PORT}")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((BEAMER_IP_ADDRESS, BEAMER_PORT))
            s.sendall(bytearray(full_payload))
            print(f"Sent command {command} to beamer")

            # save power state
            if command == 'powerOn':
                last_power_command = True
            elif command == 'powerOff':
                last_power_command = False

            return True
    except Exception as e:
        print(f"Error sending command {command} to beamer: {e}")

    return False


def check_beamer_connection() -> bool:
    try:
        with socket.create_connection((BEAMER_IP_ADDRESS, BEAMER_PORT), timeout=5):
            return True
    except Exception as e:
        print(f"Beamer connection check failed: {e}")
        return False


def on_connect(client: mqtt.Client, userdata, flags, rc, props):
    print("Connected with result code " + str(rc))
    client.subscribe("r3beamerremote/command")

    # publish online status
    client.publish("r3beamerremote/status", "online", qos=1, retain=True)
    publish_home_assistant_discovery(client)


def on_message(client: mqtt.Client, userdata, msg):
    print(f"[{msg.topic}]: {msg.payload.decode()}")
    match msg.topic:
        case "r3beamerremote/command":
            command = msg.payload.decode()
            handle_command(command)


@app.route('/')
def root():
    return app.send_static_file('index.html')


@app.route('/api/commands', methods=['GET'])
def api_commands():
    command_list = list(COMMANDS.keys())

    # group commands by prefix (split at first uppercase letter after lowercase)
    command_groups = {}
    for command in command_list:
        prefix = ''
        for i, c in enumerate(command):
            if i > 0 and c.isupper() and command[i - 1].islower():
                prefix = command[:i]
                break
        if prefix == '':
            prefix = 'other'
        if prefix not in command_groups:
            command_groups[prefix] = []
        command_groups[prefix].append(command)

    data = {
        "commands": command_list,
        "groups": command_groups
    }

    return jsonify(data)


# /api/command/<command>
@app.route('/api/command/<command_name>', methods=['POST', 'GET'])
def api_command(command_name: str):
    result = handle_command(command_name)

    return jsonify({'success': result}), 200 if result else 401


@app.route('/api/status', methods=['GET'])
def api_status():
    beamer_online = check_beamer_connection()
    status = {
        "beamer_online": beamer_online,
        "git_hash": GIT_HASH,
        "git_dirty": GIT_DIRTY,
        "last_power_command": last_power_command
    }
    return jsonify(status)


def main():
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.will_set(MQTT_WILL_TOPIC, MQTT_WILL_PAYLOAD, MQTT_WILL_QOS, MQTT_WILL_RETAIN)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTT_SERVER, MQTT_PORT, 60)

    mqtt_client.loop_start()

    app.run(host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    main()

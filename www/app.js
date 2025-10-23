let keyboard_captured = false;
let last_power_command = null;

function capitalize(text) {
    return String(text).charAt(0).toUpperCase() + String(text).slice(1);
}

function prettifyCommand(command_name) {
    const result = command_name.split(/(?=[A-Z0-9])/)

    return result.map(s => capitalize(s)).join(' ');
}

async function send_command(command_name) {
    try {
        const response = await fetch(`/api/command/${command_name}`, {
            method: 'POST'
        });
        if (!response.ok) {
            console.error(`Failed to send command ${command_name}: ${response.statusText}`);
        }
    } catch (error) {
        console.error(`Error sending command ${command_name}: ${error}`);
        alert(`Error sending command ${command_name}: ${error}`);
    }
}

async function fetch_commands() {
    try {
        const response = await fetch('/api/commands');
        if (!response.ok) {
            console.error(`Failed to fetch commands: ${response.statusText}`);
            return null;
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error(`Error fetching commands: ${error}`);
        return null;
    }
}

async function fetch_status() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            console.error(`Failed to fetch status: ${response.statusText}`);
            return null;
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error(`Error fetching status: ${error}`);
        return null;
    }
}


async function generate_interface() {
    const data = await fetch_commands();
    if (!data) {
        return;
    }

    for (const command of data.commands) {
        const el = document.getElementById(command);

        if (!el) {
            continue;
        }

        el.onclick = () => {
            send_command(command);
        };
    }

    const powerToggle = document.getElementById('powerToggle');

    if (powerToggle) {
        powerToggle.onclick = () => {
            const newState = last_power_command !== true;

            send_command(newState ? 'powerOn' : 'powerOff');

            fetch_status().then((status) => {
                if (status) {
                    last_power_command = status.last_power_command;
                }
            })
        };
    }

    const container = document.getElementById('command-interface');

    if (!container) {
        console.error('No container element found for commands', container);
        return;
    }

    for (const [group, commands] of Object.entries(data.groups)) {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'command-group';

        const groupTitle = document.createElement('h3');
        groupTitle.textContent = capitalize(group);
        groupDiv.appendChild(groupTitle);

        commands.forEach(command => {
            const button = document.createElement('button');
            button.classList.add('command-button');
            button.textContent = prettifyCommand(command);
            button.onclick = () => send_command(command);
            groupDiv.appendChild(button);
        });

        container.appendChild(groupDiv);
    }
}

function handle_capture_keyboard() {
    const button = document.getElementById('capture-keyboard');

    const btn_func = (force) => {
        if (typeof force === 'boolean') {
            keyboard_captured = force;
        } else {
            keyboard_captured = !keyboard_captured;
        }

        button.textContent = keyboard_captured ? 'Click to STOP' : 'Click to capture keyboard';
        button.style.backgroundColor = keyboard_captured ? 'red' : 'initial';

        if (keyboard_captured) {
            window.addEventListener('keydown', func);
        } else {
            window.removeEventListener('keydown', func);
        }
    };

    const func = (event) => {
        console.log(event);

        switch (event.key) {
            case 'ArrowUp':
                send_command('menuUp');
                break;
            case 'ArrowDown':
                send_command('menuDown');
                break;
            case 'ArrowLeft':
                send_command('menuLeft');
                break;
            case 'ArrowRight':
                send_command('menuRight');
                break;
            case 'Escape':
                btn_func(false);
            case 'Enter':
                send_command('menuOk');
                break;
            case 'Backspace':
                send_command('menuToggle');
                break;
            default:
                console.log('Unknown key', event);
                break;
        }
    };

    button.onclick = (e) => {
        e.target.parentNode.blur();
        btn_func();
    }
}

async function on_load() {
    // #command-interface

    /*
    GET /api/commands will return a JSON object. it has the following structure:
{
    "commands": [
        "inputHdmi",
        ...
        "menuToggle",
    ],
    "groups": {
        "input": [
            "inputHdmi",
            "inputVga",
            ...
        ],
        "menu": [
            "menuUp",
            "menuDown",
            ...
        ]
    }
}

Auto-generate a interface using the groups and commands.

The api endpoint to send commands to is /api/command/<command_name>
     */
    const status = await fetch_status();

    if (status) {
        last_power_command = status.last_power_command;
    }

    await generate_interface();

    handle_capture_keyboard();
}

window.addEventListener('DOMContentLoaded', on_load);
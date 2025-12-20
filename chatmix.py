#!/usr/bin/python3
"""   Copyright (C) 2022  birdybirdonline & awth13 - see LICENSE.md
    @ https://github.com/birdybirdonline/Linux-Arctis-7-Plus-ChatMix
    
    Contact via Github in the first instance
    https://github.com/birdybirdonline
    https://github.com/awth13
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
    """
import argparse
import getpass
import logging
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from time import sleep

import usb.core


parser = argparse.ArgumentParser(description="SteelSeries ChatMix Manager")
parser.add_argument("command", help="Command to execute [status, start, stop, restart, enable, disable, install, uninstall]")
parser.add_argument("-d", "--device", help="Specify a device ID (vendor:product)")
parser.add_argument("-f", "--force", action="store_true", help="Force the operation (e.g., overwrite existing files)")
args = parser.parse_args()

# SteelSeries USB VendorID
VENDOR_ID = 0x1038
# Known supported SteelSeries devices.  If it's not included here, it will still attempt to work automatically, but may enumerate devices wrong.
STEELSERIES_DEVICES = {
    0x220e: {
        'name': 'Arctis 7+',
        'dial': 7,
    },
    0x2022: {
        'name': 'Arctis Nova 7',
        'dial': 8,
    },
    0x227a: {
        'name': 'Nova 7 WOW Edition ',
        'dial': 7,
    }
}


def is_arctis_headset(device):
    try:
        if device.idProduct in STEELSERIES_DEVICES.keys():
            return True
        return 'Arctis' in usb.util.get_string(device, device.iProduct) and '7' in usb.util.get_string(device, device.iProduct)
    except:
        return False


class Arctis7PlusChatMix:
    mgr = None
    def __init__(self, manager: 'ChatMixManager'):
        self.mgr = manager
        # set to receive signal from systemd for termination
        signal.signal(signal.SIGTERM, self.__handle_sigterm)

        self.log = self._init_log()
        self.log.info("Initializing a7chatmix...")

        if not self.mgr.device:
            raise RuntimeError('Error: installed headset not found.')
        if self.mgr.is_root:
            raise RuntimeError('Error: must be run as logged in desktop user.')

        # select its interface and USB endpoint, and capture the endpoint address
        try:
            if STEELSERIES_DEVICES.get(self.mgr.device.idProduct, None):
                self.interface = self.mgr.device[0].interfaces()[STEELSERIES_DEVICES.get(self.mgr.device.idProduct, None)['dial']]
            else:
                # Attempts to select the interface of the ChatMix dial; usually this is the last enumerated HID interface.
                self.interface = [i for i in self.mgr.device[0].interfaces() if i.bInterfaceClass == 3][-1]
            self.interface_num = self.interface.bInterfaceNumber
            self.endpoint = self.interface.endpoints()[0]
            self.addr = self.endpoint.bEndpointAddress
        except Exception as e:
            self.log.error("""Failure to identify relevant 
            USB device's interface or endpoint. Shutting down...""")
            self.die_gracefully(trigger="identification of USB endpoint")

        # detach if the device is active
        if self.mgr.device.is_kernel_driver_active(self.interface_num):
            self.mgr.device.detach_kernel_driver(self.interface_num)

        self.VAC = self._init_VAC()

    def _init_log(self):
        log = logging.getLogger(__name__)
        log.setLevel(logging.DEBUG)
        stdout_handler = logging.StreamHandler()
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(logging.Formatter('%(levelname)8s | %(message)s'))
        log.addHandler(stdout_handler)
        return log

    def _init_VAC(self):
        """Get name of default sink, establish virtual sink
        and pipe its output to the default sink
        """

        # get the default sink id from pactl
        self.system_default_sink = os.popen("pactl get-default-sink").read().strip()
        self.log.info(f"default sink identified as {self.system_default_sink}")

        # attempt to identify an Arctis sink via pactl
        try:
            pactl_short_sinks = os.popen("pactl list short sinks").readlines()
            # grab any elements from list of pactl sinks that are Arctis 7
            arctis = re.compile('.*[aA]rctis.*7')
            arctis_sink = list(filter(arctis.match, pactl_short_sinks))[0]

            # split the arctis line on tabs (which form table given by 'pactl short sinks')
            tabs_pattern = re.compile(r'\t')
            tabs_re = re.split(tabs_pattern, arctis_sink)

            # skip first element of tabs_re (sink's ID which is not persistent)
            arctis_device = tabs_re[1]
            self.log.info(f"Arctis sink identified as {arctis_device}")
            default_sink = arctis_device

        except Exception as e:
            self.log.error("""Something wrong with Arctis definition 
            in pactl list short sinks regex matching.
            Likely no match found for device, check traceback.
            """, exc_info=True)
            return self.die_gracefully(trigger="No Arctis device match")

        # Destroy virtual sinks if they already existed incase of previous failure:
        try:
            destroy_a7p_game = os.system("pw-cli destroy Arctis_Game 2>/dev/null")
            destroy_a7p_chat = os.system("pw-cli destroy Arctis_Chat 2>/dev/null")
            if destroy_a7p_game == 0 or destroy_a7p_chat == 0:
                raise Exception
        except Exception as e:
            self.log.info("""Attempted to destroy old VAC sinks at init but none existed""")

        # Instantiate our virtual sinks - Arctis_Chat and Arctis_Game
        try:
            self.log.info("Creating VACS...")
            os.system(f"""pw-cli create-node adapter '{{ 
                factory.name=support.null-audio-sink 
                node.name=Arctis_Game 
                node.description="{self.mgr.headset_name} Game" 
                media.class=Audio/Sink 
                monitor.channel-volumes=true 
                object.linger=true 
                audio.position=[FL FR]
                }}' 1>/dev/null
            """)

            os.system(f"""pw-cli create-node adapter '{{ 
                factory.name=support.null-audio-sink 
                node.name=Arctis_Chat 
                node.description="{self.mgr.headset_name} Chat" 
                media.class=Audio/Sink 
                monitor.channel-volumes=true 
                object.linger=true 
                audio.position=[FL FR]
                }}' 1>/dev/null
            """)
        except Exception as E:
            self.log.error("""Failure to create node adapter - 
            Arctis_Chat virtual device could not be created""", exc_info=True)
            self.die_gracefully(sink_creation_fail=True, trigger="VAC node adapter")

        # route the virtual sink's L&R channels to the default system output's LR
        try:
            self.log.info("Assigning VAC sink monitors output to default device...")

            os.system(f'pw-link "Arctis_Game:monitor_FL" '
                      f'"{default_sink}:playback_FL" 1>/dev/null')

            os.system(f'pw-link "Arctis_Game:monitor_FR" '
                      f'"{default_sink}:playback_FR" 1>/dev/null')

            os.system(f'pw-link "Arctis_Chat:monitor_FL" '
                      f'"{default_sink}:playback_FL" 1>/dev/null')

            os.system(f'pw-link "Arctis_Chat:monitor_FR" '
                      f'"{default_sink}:playback_FR" 1>/dev/null')

        except Exception as e:
            self.log.error("""Couldn't create the links to 
            pipe LR from VAC to default device""", exc_info=True)
            self.die_gracefully(sink_fail=True, trigger="LR links")

        # set the default sink to Arctis Game
        os.system('pactl set-default-sink Arctis_Game')

    def start_modulator_signal(self):
        """Listen to the USB device for modulator knob's signal 
        and adjust volume accordingly
        """

        self.log.info("Reading modulator USB input started")
        self.log.info("-" * 45)
        self.log.info(f"{self.mgr.headset_name} ChatMix Enabled!")
        self.log.info("-" * 45)
        while True:
            try:
                # read the input of the USB signal. Signal is sent in 64-bit interrupt packets.
                # read_input[1] returns value to use for default device volume
                # read_input[2] returns the value to use for virtual device volume
                read_input = self.mgr.device.read(self.addr, 64)
                default_device_volume = "{}%".format(read_input[1])
                virtual_device_volume = "{}%".format(read_input[2])

                # os.system calls to issue the commands directly to pactl
                os.system(f'pactl set-sink-volume Arctis_Game {default_device_volume}')
                os.system(f'pactl set-sink-volume Arctis_Chat {virtual_device_volume}')
            except usb.core.USBTimeoutError:
                pass
            except usb.core.USBError:
                self.log.fatal("USB input/output error - likely disconnect")
                break
            except KeyboardInterrupt:
                self.die_gracefully()

    def __handle_sigterm(self, sig, frame):
        self.die_gracefully()

    def die_gracefully(self, sink_creation_fail=False, trigger=None, **kwargs):
        """Kill the process and remove the VACs
        on fatal exceptions or SIGTERM / SIGINT
        """

        self.log.info('Cleanup on shutdown')
        os.system(f"pactl set-default-sink {self.system_default_sink}")

        # cleanup virtual sinks if they exist
        if sink_creation_fail == False:
            self.log.info("Destroying virtual sinks...")
            os.system("pw-cli destroy Arctis_Game 1>/dev/null")
            os.system("pw-cli destroy Arctis_Chat 1>/dev/null")

        if trigger is not None:
            self.log.info("-" * 45)
            self.log.fatal("Failure reason: " + trigger)
            self.log.info("-" * 45)
            sys.exit(1)
        else:
            self.log.info("-" * 45)
            self.log.info(f"{self.mgr.headset_name} ChatMix shut down gracefully... Bye Bye!")
            self.log.info("-" * 45)
            sys.exit(0)


class ChatMixManager:
    device = None
    user = {'name': 'root', 'uid': 0}
    headset_name = None
    headset_id = None
    service = None

    @property
    def is_root(self):
        return self.user['uid'] == 0

    def find_desktop_user(self):
        self.user['uid'] = int(os.environ.get('SUDO_UID', os.getuid()))
        self.user['name'] = os.environ.get('SUDO_USER', getpass.getuser())

    def find_headset(self, device_id=None):
        if device_id:
            dev = usb.core.find(idVendor=int(device_id.split(':')[0], 16), idProduct=int(device_id.split(':')[1], 16))
        else:
            dev = usb.core.find(idVendor=VENDOR_ID, custom_match=is_arctis_headset)
        if dev:
            self.device = dev
            self.headset_name = usb.util.get_string(dev, dev.iProduct)
            self.headset_id = usb.util.get_string(dev, dev.iProduct).lower().replace(' ', '')
            print(f'SteelSeries {self.headset_name} headset found.')

    def install_udev_rules(self):
        udev_path = Path("/etc/udev/rules.d/")
        rules_path = udev_path / f"{self.user['uid']}-steeleries-{self.headset_id}.rules"
        print(f'Installing udev rules for {usb.util.get_string(self.device, self.device.iProduct)} to {rules_path}')
        contents = f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{VENDOR_ID:04x}", ATTRS{{idProduct}}=="{self.device.idProduct:04x}", OWNER="{self.user['name']}", GROUP="{self.user['name']}", MODE="0664"\n' \
            f'ACTION=="add", SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{VENDOR_ID:04x}", ATTRS{{idProduct}}=="{self.device.idProduct:04x}", TAG+="systemd", ENV{{SYSTEMD_ALIAS}}="/dev/arctis7"\n' \
            f'ACTION=="remove", SUBSYSTEM=="usb", ENV{{PRODUCT}}=="{VENDOR_ID:04x}/{self.device.idProduct:04x}/*", TAG+="systemd"\n'
        with open(rules_path, "w") as f:
            f.write(contents)
        subprocess.run(['sudo', 'udevadm', 'control', '--reload'], check=True)
        subprocess.run(['sudo', 'udevadm', 'trigger'], check=True)
        print(f'udev rules installed for {self.user['name']}-{self.headset_id} . A reboot will be required for changes to take effect.')

    def uninstall_udev_rules(self):
        udev_path = Path("/etc/udev/rules.d/")
        rules_path = udev_path / f"{self.user['uid']}-steeleries-{self.headset_id}.rules"
        if rules_path.exists():
            rules_path.unlink()
            subprocess.run(['sudo', 'udevadm', 'control', '--reload'])
            subprocess.run(['sudo', 'udevadm', 'trigger'])
            print(f'udev rules for {self.user['name']}-{self.headset_id} removed. A reboot will be required for changes to take effect.')

    def install_systemd_unit(self):
        contents = f'[Unit]\n' \
                f'Description={self.headset_name} ChatMix\n' \
                f'#BindsTo=dev-arctis7.device\n' \
                f'After=dev-arctis7.device\n' \
                f'StartLimitIntervalSec=1m\n' \
                f'StartLimitBurst=5\n' \
                '\n' \
                f'[Service]\n' \
                f'Type=simple\n' \
                f'ExecStart={Path(__file__).resolve()} daemon --device {self.device.idVendor:04x}:{self.device.idProduct:04x}\n' \
                f'Restart=on-failure\n' \
                f'RestartSec=5\n' \
                '\n' \
                f'[Install]\n' \
                f'WantedBy=dev-arctis7.device\n'
        if not self.systemd_unit.parent.exists():
            self.systemd_unit.parent.mkdir(parents=True, exist_ok=True)
        if not self.systemd_unit.exists() or args.force:
            print(f'Installing systemd unit for {usb.util.get_string(self.device, self.device.iProduct)} to {self.systemd_unit}')
            with open(self.systemd_unit, 'w') as f:
                f.write(contents)
            os.chmod(self.systemd_unit, 0o644)
            os.chown(self.systemd_unit, self.user['uid'], self.user['uid'])
            subprocess.run(['sudo', 'systemctl', '--user', f'--machine={self.user['name']}@.host', 'enable', self.systemd_unit.name], check=True)
        else:
            print(f'{self.systemd_unit.name} already exists in systemd user directory.  Skipping installation. (Use -f to overwrite.)')

    def uninstall_systemd_unit(self):
        systemd_dir = Path('/home') / self.user['name'] / '.config' / 'systemd' / 'user'
        filename = f'chatmix-{self.headset_id}.service'
        file_path = systemd_dir / filename
        subprocess.run(['sudo', 'systemctl', '--user', f'--machine={self.user['name']}@.host', 'disable', filename])
        if file_path.exists():
            file_path.unlink()
            print(f'{filename} already exists in systemd user directory.  Skipping installation. (Use -f to overwrite.)')

    def run_chatmix(self):
        a7pcm_service = Arctis7PlusChatMix(self)
        self.service = a7pcm_service
        a7pcm_service.start_modulator_signal()

    def print_status(self):
        self.find_desktop_user()
        self.find_headset(args.device)
        if self.device is None:
            print("No headsets found.")

        if self.systemd_unit.exists():
            subprocess.run(['systemctl', '--user', f'--machine={self.user['name']}@.host', 'status', self.systemd_unit.name], check=True)

    @property
    def systemd_unit(self):
        systemd_dir = Path('/home') / self.user['name'] / '.config' / 'systemd' / 'user'
        filename = f'chatmix-{self.headset_id}.service'
        return systemd_dir / filename



def run_main():
    mgr = ChatMixManager()

    if args.command == 'install':
        mgr.find_desktop_user()
        if os.getuid() != 0:
            print('Error: This must be ran as a desktop user with sudo.')
            sys.exit(1)
        if mgr.is_root:
            print('You cannot install a headset as root. Run as a logged in desktop user with sudo.')
            sys.exit(1)
        mgr.find_headset(args.device)
        mgr.install_udev_rules()
        mgr.install_systemd_unit()

    elif args.command == 'uninstall':
        mgr.find_desktop_user()
        if os.getuid() != 0:
            print('Error: This must be ran as a desktop user with sudo.')
            sys.exit(1)
        if mgr.is_root:
            print('You cannot uninstall a headset as root. Run as a logged in desktop user with sudo.')
            sys.exit(1)
        mgr.find_headset(args.device)
        mgr.uninstall_udev_rules()
        mgr.uninstall_systemd_unit()

    elif args.command == 'purge':
        mgr.find_desktop_user()
        if os.getuid() != 0:
            print('Error: This must be ran as a desktop user with sudo.')
            sys.exit(1)
        if mgr.is_root:
            print('Error: run as a logged in desktop user with sudo.')
            sys.exit(1)
        # TODO: purge all systemd units and udev rules for the user. Maybe have --all-users, -a to do everyone

    elif args.command in ('start', 'stop', 'restart', 'enable', 'disable'):
        mgr.find_desktop_user()
        if mgr.is_root:
            print('Error: This must be ran as a logged in desktop user.')
            sys.exit(1)
        mgr.find_headset(args.device)
        if mgr.device:
            service_name = f'chatmix-{mgr.headset_id}.service'
            subprocess.run(['systemctl', '--user', f'--machine={mgr.user['name']}@.host', args.command, service_name], check=True)
            print(f'{args.command.capitalize()}ed {service_name}')
        else:
            print('No headset found.')
            sys.exit(1)

    elif args.command == 'status':
        mgr.print_status()

    elif args.command == 'daemon':
        mgr.find_desktop_user()
        while True:
            try:
                if not mgr.device:
                    mgr.find_headset(args.device)
                    if mgr.device:
                        print(f'SteelSeries {mgr.headset_name} headset found.')
                        mgr.run_chatmix()
                sleep(3)
            except KeyboardInterrupt:
                exit(0)
            except Exception as e:
                print(e)
                if mgr.service:
                    try:
                        mgr.service.die_gracefully()
                    except:
                        pass
                exit(1)

    elif args.command == 'help':
            parser.print_help()
            sys.exit(0)

    else:
        print('unknown command.')
        sys.exit(1)

if __name__ == '__main__':
    run_main()
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

import logging
import os
import re
import signal
import sys

import usb.core

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
    def __init__(self):

        # set to receive signal from systemd for termination
        signal.signal(signal.SIGTERM, self.__handle_sigterm)

        self.log = self._init_log()
        self.log.info("Initializing a7chatmix...")

        # Grabs first Arctis device. Only supports the Arctis 7 family of devices
        try:
            self.dev = usb.core.find(idVendor=VENDOR_ID, custom_match=is_arctis_headset)
            self.name = usb.util.get_string(self.dev, self.dev.iProduct)

            # print(self.dev)
            # print(self.dev[0].interfaces())
            # print(self.dev[0].interfaces()[-1])
            # exit(0)
        except Exception as e:
            self.log.error("""Failed to identify the Arctis 7 device.
            Please ensure it is connected.\n
            Please note: This program only supports the Arctis 7 family of devices.""")
            self.die_gracefully(trigger="Couldn't find arctis7 model")

        # select its interface and USB endpoint, and capture the endpoint address
        try:
            if STEELSERIES_DEVICES.get(self.dev.idProduct, None):
                self.interface = self.dev[0].interfaces()[STEELSERIES_DEVICES.get(self.dev.idProduct, None)['dial']]
            else:
                # Attempts to select the interface of the ChatMix dial; usually this is the last enumerated HID interface.
                self.interface = [i for i in self.dev[0].interfaces() if i.bInterfaceClass == 3][-1]
            self.interface_num = self.interface.bInterfaceNumber
            self.endpoint = self.interface.endpoints()[0]
            self.addr = self.endpoint.bEndpointAddress
        except Exception as e:
            self.log.error("""Failure to identify relevant 
            USB device's interface or endpoint. Shutting down...""")
            self.die_gracefully(trigger="identification of USB endpoint")

        # detach if the device is active
        if self.dev.is_kernel_driver_active(self.interface_num):
            self.dev.detach_kernel_driver(self.interface_num)

        self.VAC = self._init_VAC()

    def _init_log(self):
        log = logging.getLogger(__name__)
        log.setLevel(logging.DEBUG)
        stdout_handler = logging.StreamHandler()
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(logging.Formatter('%(levelname)8s | %(message)s'))
        log.addHandler(stdout_handler)
        return (log)

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
            self.die_gracefully(trigger="No Arctis device match")

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
                node.description="{self.name} Game" 
                media.class=Audio/Sink 
                monitor.channel-volumes=true 
                object.linger=true 
                audio.position=[FL FR]
                }}' 1>/dev/null
            """)

            os.system(f"""pw-cli create-node adapter '{{ 
                factory.name=support.null-audio-sink 
                node.name=Arctis_Chat 
                node.description="{self.name} Chat" 
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
        self.log.info(f"{self.name} ChatMix Enabled!")
        self.log.info("-" * 45)
        while True:
            try:
                # read the input of the USB signal. Signal is sent in 64-bit interrupt packets.
                # read_input[1] returns value to use for default device volume
                # read_input[2] returns the value to use for virtual device volume
                read_input = self.dev.read(self.addr, 64)
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

    def die_gracefully(self, sink_creation_fail=False, trigger=None):
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
            self.log.info(f"{self.name} ChatMix shut down gracefully... Bye Bye!")
            self.log.info("-" * 45)
            sys.exit(0)


# init
if __name__ == '__main__':
    a7pcm_service = Arctis7PlusChatMix()
    a7pcm_service.start_modulator_signal()

# Linux SteelSeries ChatMix

Forked from [awth13/Linux-Arctis-7-Plus-ChatMix](https://github.com/awth13/Linux-Arctis-7-Plus-ChatMix).

##***Important Licensing Notice**##

`Linux-Arctis-7-Plus-Chatmix` uses the GPL license. While the GPL license does permit commercial use,
it is **strongly discouraged** to reuse the work herein for any for-profit purpose as it relates to the usage
of a third party proprietary hardware device. 

The device itself has not been reverse-engineered for this purpose, nor has the proprietary GG Sonar Software typically
required to use it. 


## Overview
<br>
The SteelSeries Arctis series of headsets include a hardware modulation knob for 'chatmix' on the headset.
This allows the user to 'mix' the volume of two different devices on their system, named "Game" and "Chat".

On older Arctis models (e.g. Arctis 7), the headset would be detected as two individual hardware devices by
the host operating system and would assign them as such accordingly, allowing the user to specify which device to
use and where.

**Typical use case:** "Chat" for voicechat in games and VOIP/comms software, and "Game" for system / music etc.

On newer SteelSeries models like the Arctis 7+ and Nova 7 WOW Edition, this two-device differentiation no longer exists, and the host OS will only recognize a single device.
If the user wishes to utilize the chatmix modulation knob, they *must* install the SteelSeries proprietary GG software. This
software does not currently support Linux.

This script provides a basic workaround for this problem for Linux users. It creates a Virtual Audio Cable (VAC) pair called "Arctis 7+ Chat"
and "Arctis 7+ Game" respectively, which the user can then assign accordingly as they would have done with an older Arctis model.

**Known Supported Devices:**
- SteelSeries Arctis 7+ (Product ID: 0x220e)
- SteelSeries Nova 7 WOW Edition (Product ID: 0x227a)
- SteelSeries Nova 7 (Product ID: 0x2202)
- It should work with any SteelSeries Arctis 7 family headset

The script listens to the headset's USB dongle signals and interprets them in a way that can be meaningfully converted
to adjust the audio when the user moves the dial on the headset.

###  ###

At startup of the daemon the user must disconnect and reconnect the USB dongle from the machine. The headset will be automatically set to the default device when the daemon starts.

<br>

## Requirements
<br>

- A distro using systemd and PipeWire audio engine
  - Examples:
    - Ubuntu 22+
    - Debian 12+
    - Fedora 34+
- PulseAudio utils (Available as `pulseaudio-utils` in most distros)
- Python3
- PyUSB (available as `pyusb` in pip or `python3-usb` in various distros.)

In order for the VAC to be initialized and for the volumes to be controlled, the system requires **Pipewire** (and the underlying **PulseAudio**)
which are both fairly common on modern Linux systems out of the box.

<br>

## Installation
<br>

Run `install.sh` as root to copy the binary.

After that, you can run `sudo chatmix install` ad a logged in desktop user to setup the service for the current user with a detected headset. Reboot once finished.

After you reboot, the service would have already been enabled and your ChatMix should now be working.

You can check the status using `chatmix status`.

<br>

## Implementation - How it works

From Linux-Arctis-7-Plus-ChatMix:
> The service first initializes the VAC by making direct calls to PulseWire `pw-cli` to create `nodes` and link them to the default audio device.
> 
> The service relies on the [PyUSB](https://github.com/walac/pyusb) package to read interrupt transfers from the headset's USB dongle. 
> 
> The headset sends three bytes, the second and third of which are the volume values for the dial's two directions (toward 'Chat' down, toward 'Game' up). 
> 
> The volumes are processed by the service and passed to the audio system via `pactl`. 
> 
> The service will automatically set "Arctis 7 Game" as the default device on startup.

The `chatmix` binary is a simple python script wrapper around that to make it easier to install/manage the service and udev rules.


# Acknowledgements

With great thanks to:
- [awth13](https://github.com/awth13), especially for contributions in creation of our rules.d and systemd configuration and for wrestling with ALSA in our early attempts
- [Alexandra Zaharia's](https://github.com/alexandra-zaharia) excellent [article](https://alexandra-zaharia.github.io/posts/stopping-python-systemd-service-cleanly) for the clear advice on good practices for sigterm SIGINT/SIGTERM & logging
- [PyUSB's creators](https://github.com/pyusb) for [PyUSB](https://github.com/pyusb/pyusb) itself
- Honorable mention: [this reddit thread for clueing me in to reading the USB input!](https://www.reddit.com/r/steelseries/comments/s4uzos/arctis_7_on_linux_sonar_workaround/hu51jjy/)


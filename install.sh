#!/bin/bash
#     Copyright (C) 2022  birdybirdonline & awth13 - see LICENSE.md
#     @ https://github.com/birdybirdonline/Linux-Arctis-7-Plus-ChatMix
    
#     Contact via Github in the first instance
#     https://github.com/birdybirdonline
#     https://github.com/awth13


if [ "$(id -u)" -ne 0 ]; then
    echo "Please run the install script as root."
    exit 1
fi

echo "Installing Arctis 7+ ChatMix."
SCRIPT="chatmix.py"
SCRIPT_DIR="/usr/local/bin/"

if [ -f "chatmix.py" ]; then # Check if binary is present and install manually
    echo "Installing script to ${SCRIPT_DIR}${SCRIPT}."
    cp "$SCRIPT" "$SCRIPT_DIR"
else
    echo "Installing from GitHub..."
    curl -L -o "${SCRIPT_DIR}chatmix" "https://raw.githubusercontent.com/cclloyd/linux-steelseries-chatmix/refs/heads/main/chatmix.py"
    if [ $? -eq 0 ]; then
        echo "Successfully downloaded chatmix.py to ${SCRIPT_DIR}"
    else
        echo "Failed to download install.sh"
        exit 1
    fi
fi


#echo "Installing script to ${SCRIPT_DIR}${SCRIPT}."
#if [[ ! -d "$SCRIPT_DIR" ]]; then
#    mkdir -vp $SCRIPT_DIR || \
#        { echo "FATAL: Failed to create $SCRIPT_DIR" ; cleanup ; exit 1;}
#fi
#cp "$SCRIPT" "$SCRIPT_DIR"

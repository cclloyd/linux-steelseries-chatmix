#!/bin/bash
#     Copyright (C) 2022  birdybirdonline & awth13 & cclloyd - see LICENSE.md
#     @ https://github.com/birdybirdonline/Linux-Arctis-7-Plus-ChatMix
    
#     Contact via Github in the first instance
#     https://github.com/cclloyd
#     https://github.com/birdybirdonline
#     https://github.com/awth13

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run the install script as root."
    exit 1
fi

echo "Installing Arctis 7 ChatMix"
SCRIPT_DIR="/usr/local/bin/"

if [ -f "chatmix.py" ]; then # Check if binary is present and install manually
    echo "Installing local script to ${SCRIPT_DIR}chatmix."
    cp "chatmix.py" "${SCRIPT_DIR}chatmix"
    chmod +x "${SCRIPT_DIR}chatmix"
else
    echo "Installing from GitHub..."
    curl -L -o "${SCRIPT_DIR}chatmix" "https://raw.githubusercontent.com/cclloyd/linux-steelseries-chatmix/refs/heads/main/chatmix.py"
    if [ $? -eq 0 ]; then
        echo "Successfully downloaded chatmix.py to ${SCRIPT_DIR}"
        chmod +x "${SCRIPT_DIR}chatmix"
    else
        echo "Failed to download chatmix.py. Try cloning the repo and running locally instead."
        exit 1
    fi
fi


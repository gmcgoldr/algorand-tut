#!/bin/bash

sudo apt-get update
sudo apt-get install -y gnupg2 curl software-properties-common

curl -O https://releases.algorand.com/key.pub
sudo apt-key add key.pub
rm -f key.pub
sudo add-apt-repository "deb [arch=amd64] https://releases.algorand.com/deb/ stable main"

sudo apt-get update
sudo apt-get install algorand
sudo pip install -U py-algorand-sdk pyteal algo-app-dev[dev]

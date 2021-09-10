#!/bin/bash

# Start the `algod` daemon in the background
sudo -u algorand algod -d /var/lib/algorand/net1/Primary &
# And start the `kmd` daemon blocking. Not cleary why it must point to the 
# specific version directory, but this is where the genesis wallet data resides
sudo -u algorand kmd -d /var/lib/algorand/net1/Primary/kmd-v0.5
# NOTE: this isn't a great solution, but this script is just a quick and dirty
# way to get the two daemons running together without systemd
sudo killall -u algorand


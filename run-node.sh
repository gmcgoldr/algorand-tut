#!/bin/bash

# Start the `algod` daemon in the background
sudo -u algorand algod -d /var/lib/algorand/net1/Primary &
# And start the `kmd` daemon blocking. Not cleary why it must point to the 
# specific version directory, but this is where the genesis wallet data resides
sudo -u algorand kmd -d /var/lib/algorand/net1/Primary/kmd-v0.5

# not sure why, but algod is also killed when kmd exits, but in case this is
# system dependent, kill background jobs (quietly for when algod has stopped)
jobs -p | xargs -r sudo kill > /dev/null 2>&1


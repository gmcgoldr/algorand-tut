#!/bin/bash

if [[ -z $1 ]]; then
	echo "usage: run-node.sh {private,dev}"
    exit -1
fi

network=$1

# start `algod` and `kmd` daemons in the background
sudo -u algorand goal -d /var/lib/algorand/net_${network}/Primary node start
sudo -u algorand goal -d /var/lib/algorand/net_${network}/Primary kmd start

# wait for user input
read -n 1 -p "Press any key to stop "
# stop the daemons
sudo -u algorand goal -d /var/lib/algorand/net_${network}/Primary node stop
sudo -u algorand goal -d /var/lib/algorand/net_${network}/Primary kmd stop

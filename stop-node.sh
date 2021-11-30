#!/bin/bash

if [[ -z $1 ]]; then
	echo "usage: stop-node.sh {private,dev}"
    exit -1
fi

network=$1

sudo -u algorand goal -d /var/lib/algorand/net_${network}/Primary node stop
sudo -u algorand goal -d /var/lib/algorand/net_${network}/Primary kmd stop

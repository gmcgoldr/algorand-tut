#!/bin/bash

if [[ -z $1 ]]; then
	echo "usage: make-node.sh {private,dev}"
    exit -1
fi

network=$1

# overwrite the previous network instance
sudo -u algorand rm -rf /var/lib/algorand/net_${network}
# use the provided network template to initialize a network instance
sudo -u algorand goal network create \
	-r /var/lib/algorand/net_${network} \
	-n private \
	-t data/network_${network}.json

if [[ $network == "dev" ]]; then
	# enable dev APIs (compile, dry run) for algod
	sudo -u algorand algocfg \
		-d /var/lib/algorand/net_${network}/Primary \
		set -p EnableDeveloperAPI -v true
fi

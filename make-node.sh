#!/bin/bash

sudo -u algorand cp data/network_template.json /var/lib/algorand
sudo -u algorand rm -rf /var/lib/algorand/net1
sudo -u algorand goal network create \
	-r /var/lib/algorand/net1 \
	-n private \
	-t /var/lib/algorand/network_template.json

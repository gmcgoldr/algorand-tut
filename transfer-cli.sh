#!/bin/bash

if [[ -z $1 ]]; then
	echo "usage: transfer-cli.sh note_data_dir"
    exit -1
fi

dir=$1

# Becaues the algorand user doesn't have a password, can't su directly to it
# without use account configuration, use sudo instead to run each command from
# that account
pre="sudo -u algorand"

# Make sure algod is interact with the network
printf "Network status:\n"
$pre goal network -r /var/lib/algorand/net1 status

# Building the network added a wallet to manage the account specified in the
# genesis configuration
printf "\nWallet and account from genesis:\n"
$pre goal -d $dir wallet list
$pre goal -d $dir account list

# The concensus should be running as there is an online account
printf "\nBlock 0:\n"
$pre goal -d $dir ledger block 0

# Add a new wallet. If a password is entered, it will be encrypted on disk.
printf "\nAdd Wallet2 (password can be empty):\n"
$pre goal -d $dir wallet new Wallet2
$pre goal -d $dir wallet list

# Create a new account so that some transactions can take place
printf "\nAdd account to Wallet2:\n"
$pre goal -d $dir account -w Wallet2 new

# List the default wallet and get the first address
genesis_address=$($pre goal -d $dir account list | head -n 1 | awk -F' ' '{print $3}')
# List the new wallet and get the last address
new_address=$($pre goal -d $dir account -w Wallet2 list | tail -n 1 | awk -F' ' '{print $3}')
# NOTE: the CLI output shouldn't be treated as a contract or API, so expect the
# pipe processing to fail in future versions.

printf "\nAccount balances:"
printf "\nGenesis: %s" "$($pre goal -d $dir account balance -a $genesis_address)"
printf "\nNew: %s" "$($pre goal -d $dir account balance -a $new_address)"

# The `clerk` command manages transactions. It uses the default wallet unless
# otherwise specified. The wallet manages the private keys for its accounts,
# so ther is no need to enter the private key for the sending address. However,
# if the wallet was encrypted, a password would be required to access it.
printf "\nMove some Algos:\n"
$pre goal -d $dir clerk send -a 1000000 -f $genesis_address -t $new_address
printf "\nGenesis: %s" "$($pre goal -d $dir account balance -a $genesis_address)"
printf "\nNew: %s" "$($pre goal -d $dir account balance -a $new_address)"
printf "\n"

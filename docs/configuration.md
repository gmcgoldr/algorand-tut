---
layout: page
title: Configuration
---

The following explains how to install and configure your system to build and test smart contracts.

## Key terms

Following is some terminology which is used throughout this tutorial:

- `algod`:
  the Alogrand daemon which runs a node on a network.
- `kmd`:
  the key manager daemon which manages account information,
  including private keys,
  and relay that information to a node.
- node:
  a machine participating in the Algorand protocol,
  and communicating with other nodes on a network.
  The nodes keeps a copy of the ledger synchronized with the network,
  and can propose modifications to the ledger (transactions).
- network:
  a group of nodes participating in a version of the Algorand protocol with a common genesis block.
  The Algorand tools keep track of three networks: MainNet, TestNet and BetaNet.
  MainNet and TestNet follow the same protocol,
  but have different genesis blocks and thus different histories.
  BetaNet follows a different protocol version.
- account:
  a public / public key pair which can be used in the Algorand protocol.
  Accounts on the ledger can:
  track ownership of assets,
  track state of smart contracts,
  and authorize transactions.

You can find more definitions in the [glossary]({{ site.baseurl }}{% link glossary.md %}).

## Installation

These instructions should work on a recent (> 18.04) Ubuntu environment.
It is also possible to install Algorand using a Docker container,
so that no additional system configuration is required.
More at <https://developer.algorand.org/docs/run-a-node/setup/install/>.

All installation steps can be executed with `./install.sh`.

### Pre-requisites

```bash
sudo apt-get update
sudo apt-get install -y gnupg2 curl software-properties-common
```

### Install the node implementation and tools

Add to software sources so it can be managed with `apt`:

```bash
curl -O https://releases.algorand.com/key.pub
sudo apt-key add key.pub
rm -f key.pub
sudo add-apt-repository "deb [arch=amd64] https://releases.algorand.com/deb/ stable main"
```

Install:

```bash
sudo apt-get update
sudo apt-get install algorand
```

The `algorand` package contains the Algorand node implementation,
and CLI tools to configure and interact with the networks and nodes.

### Install the SDK

Install python dependencies
(as the `algorand` user which will be running the python scripts):

```bash
sudo -u algorand pip install -r requirements.txt
```

NOTE: `sudo -u algorand` will be used frequently to interact with the operating
system as the `algorand` user. The home directory of this account is set to
`/var/lib/algorand` during installation which conveniently means `algorand`
related configuration (e.g. the python libraries) are installed in that location.

The `goal` CLI is included in the `algorand` package and is fairly ubiquitous.
It's documentation is found at:
<https://developer.algorand.org/docs/reference/cli/goal/goal/>.

### Install PyTeal Utils

```bash
sudo pip install -U algo-app-dev[dev]
```

This command installs `algo-app-dev` from PyPI,
and downloads the dev dependencies (needed for testing).

NOTE: it is recommended to install this package globally (using `sudo`),
since this means both your account,
and the `algorand` account have access to the package libraries and binaries.
It is possible to install it in a virtual environment,
but in this case some additional system configuration is required to ensure the `algorand` account has access to the virtual environment.

## Create a node

### Create a private network

In order to deploy an app on a network,
you need to be able to make calls to a node which is connected to an Algorand network.
You can either use a 3rd party online service which will give you access to a running node,
or you can run a node directly on your local machine.

In this tutorial, you will configure and run a node locally,
and have it connect to your own private network.
The advantages are that your work is fully self-contained,
you can inspect and reason about all the ledger data,
and you don't need to spend time and hard drive space to synchronize with an existing ledger.

The `algorand` package includes the `goal` CLI which interacts with node-related APIs.
It also can create the node data required to run the node on a local network.
The command is `goal network create` and requires a network template.

Here is a minimal private network template.
More: <https://developer.algorand.org/tutorials/create-private-network/#network-template-overview>.

```json
{
    "Genesis": {
        "NetworkName": "",
        "Wallets": [
            {
                "Name": "Wallet1",
                "Stake": 100,
                "Online": true
            }
        ]
    },
    "Nodes": [
        {
            "Name": "Primary",
            "IsRelay": true,
            "Wallets": [
                {
                    "Name": "Wallet1",
                    "ParticipationOnly": false
                }
            ]
        }
    ]
}
```

This template instructs `goal` to setup node data with:

- a genesis block with a single account,
- the account keys are managed in `Wallet1`,
- the account has 100% of the stake,
- the account is online meaning it is available for participating in consensus,
- a single node in the network,
- the node can serve as a relay for other nodes,
- the node hosts the wallet `Wallet1`,
- the keys in `Wallet1` can participate in both consensus as well as transactions.

Some notes on those choices:

- If no node is online, the network will stay stuck on the genesis block.
- The stake must add up to `100%`.
- The name of the node is arbitrary,
  and its data will be placed in a directory with its name.
- The documentation says every network needs one relay node to allow non-relay nodes to communicate.
  But this seems to work fine if the node is not marked `IsRelay`,
  given that no other nodes need to connect to the network.

To create the private dev network (which will be used subsequently),
run the `algo-app-dev` command `sudo -u algorand aad-make-node private_dev`.

In effect, it runs these two commands:

```bash
goal network create --rootdir $data_path --network $name --template $template_path
algocfg -d ${data_path}/Primary set -p EnableDeveloperAPI -v true
```

And `$template_path` is the path to a file based on the above network configuration,
with dev mode enabled.

### Dev mode

A network can be configured in *dev mode* (as in the above step).
A network in dev mode won't perform full consensus,
but will instead commit every transaction instantly.

This is tremendously useful when debugging a smart contract:
instead of sending a transaction and waiting for the node to complete a consensus round
(which takes a few seconds),
the transaction is immediately executed in its own block.

This allows for both low latency execution (good for testing),
and deterministic blocks.
However, these blocks do not resemble real blocks,
and subtle errors could arise if testing only in dev mode
(e.g. you won't see the effect of multiple transactions interacting with a stateful contract in the same block).

In order to enable dev mode in the network template,
set `ConsensusProtocol` to `future`,
and `DevMode` to `true`.

## Run the node

The `algorand` Debian package expects its daemons to be managed by `systemd`.
Under normal circumstances,
the process is spawned and kept alive by `systemd`.

However, for testing purposes, and for environments lacking `systemd` (e.g. WSL2),
it can be useful to start the node daemons directly using `goal`:

```bash
sudo -u algorand goal -d $node_data_dir node start
sudo -u algorand goal -d $node_data_dir kmd start
```

This can also be done with the `algo-app-dev` command:

```bash
sudo -u algorand aad-run-node private_dev start
```

### Data directory

The `-d` flag is used in many commands to specify a data directory.
In this case,
the node is being told to run with the data created by `goal` when the network was built,
which connects the node to the network.

The key manager runs on a node and manages wallets.
It allows the node to use the private keys held in those wallets.
Otherwise, when the node needs to an account's signature,
those private keys would need to be passed through the node's API.

Next in the tutorial: [transactions]({{ site.baseurl }}{% link transactions.md %}).

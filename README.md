# An Algorand Tutorial

This is part tutorial, part exploration of the Alogrand developer experience.
This code base started out with the objective:
learn enough Algorand tooling and APIs to write a smart contract with voting mechanics,
and execute it on a ledger.

A very quick foreword on Algorand for the uninitiated:
Algorand is a pure proof-of-stake blockchain
(the Algorand Foundation is working to become carbon-*negative*)
with deployed smart contract functionality.
As a developer, it is attractive because the technology so far is proving robust,
its smart contract language avoids pitfalls discovered in precursor technologies,
and it is operationally simple enough that a node can be run on commodity hardware.
That is not to say that it is the be-all and end-all of blockchains,
but it's looking like a good place to spend some brain cycles.

In its current form, here's what the tutorial will walk you through:

1. Install the Algorand networking and dev tools
2. Create a private Algorand network and run a node
3. Setup accounts and make transfers using CLIs and the Python SDK
4. Write a periodic payment contract
5. ~~Write a distributed treasury contract with voting~~

All steps are code are tested on Ubuntu 20.04 running in WSL2,
with `python` 3.8,
and `algod` 2.10.1.
The steps should translate well to a native Ubuntu 20.04 installation,
and can probably be translated fairly well to other Linux distributions,
given that you have good familiarity with that distribution's tooling.

For a good overview of how the different components of an Algorand development environment interact,
and for a primer one some Algorand and general blockchain terminology, see:
<https://developer.algorand.org/docs/build-apps/setup/>.

For more terminology, see the last section of this document.

## Installation

This section will guide you through installing a node.
These instructions should work on an Ubuntu 20.04 environment.
It is also possible to install algorand using in a Docker container,
so that no additional system configuration is required.
More at <https://developer.algorand.org/docs/run-a-node/setup/install/>.

### Install pre-requisites

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

Intall:

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
sudu -u algorand pip install -U py-algorand-sdk pyteal
```

NOTE: `sudo -u algorand` will be used frequently to interact with the operating
system as the `algorand` user. The home directory of this account is set to
`/var/lib/algorand` during installation which conveniently means `algorand`
related configuration (e.g. the python libraries) are installed in that location.

The `goal` CLI is included in the `algorand` package and is fairly ubiquitous.
It's documentation is found at:
<https://developer.algorand.org/docs/reference/cli/goal/goal/>.

## Building a private network

One of the goals stated in the introduction is to deploy a smart contract onto a ledger.
In order to do this, you need to be able to make calls to a node which is connected to an Algorand network.
You can either use a 3rd party online service which will give you access to a running node,
or you can install a node locally.
And the node needs to talk to a network,
which could be the: main net, test net, beta net, or a private network.

In this tutorial, you will configure and run a node locally,
and have it connect to your own private network.
The advantages are that your work is fully self-contained,
you can inspect and reason about all the ledge data,
and you don't need to spend lots of time and hard drive space to synchronize with an existing ledger.

### Create the private network

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
- the keys in `Wallet1` can participate in both consensus as well as general transactions.

Some notes on these choices:

- If no node is online, the network will stay stuck on the genesis block.
- The stake must add up to `100%`.
- The name of the node is arbitrary,
  and its data will be placed in a directory with its name.
- The documentation says every network needs one relay node,
  as non-relay nodes will need a relay node to communicate with the rest of the network.
  But this seems to work fine if the node is not marked `IsRelay`,
  so it seems a single-node network is the exception.

To create the private network, run the provided script `bash make-node.sh`.

## Run the node

The `algorand` Debian package exepcts its daemons to be managed by `systemd`.
But `systemd` is not running on WSL2.
So, in what follows, the daemons will be run directly from the command line.
If you are following along on a native Ubuntu installation,
feel free to use `systemd` to start and stop the daemons,
or just to keep them stopped in `systemd` and follow along here.

Run the node daemon `algod` and the key manager daemond `kmd` in the background:

```bash
sudo -u algorand algod -d /var/lib/algorand/net1/Primary &
sudo -u algorand kmd -d /var/lib/algorand/net1/Primary/kmd-v0.5 &
```

### Data directory

The `-d` flag is used in many commands to specify a data directory.
In this case,
the node is being told to run with the data created by `goal`,
which connects the node to the private network.

The key manager runs on a node and manages wallets.
It allows the node to use the private keys held in those wallets.
Otherwise, those private keys would need to be passed to the node through its API when the node needs to use an account's private key,
for example to sign a transaction.

## Interacting and transferring

Some CLI interactions are demoed in `transfer-cli.sh`,
which adds an account and transfers some Algos.
Programatic access is demoed in `transfer-sdk.py`.
More: <https://developer.algorand.org/docs/build-apps/hello_world/>.

Run the scripts:

```bash
bash transfer-cli.sh
sudo -u algorand python3 transfer-sdk.py /var/lib/algorand/net1/Primary
```

## Creating a smart contract

A TEAL program (a.k.a. contract) is evaluated with a transaction data structure
as its input (it can have more inputs), and outputs a single boolean which
either approves or rejects the transactions.
More:
<https://developer.algorand.org/docs/reference/teal/specification/>

### Stateless contracts

A TEAL program compiled in "signature" mode is stateless.
Its inputs are the transaction fields,
as well as some globla fields,
and it simply signs or does not sign the transaction depending on the result of its logic.

One way to think of these contracts it that they are delegates of some account.
The account signs the contract,
and the contract can sign other transactions on the behalf of the account.

Another way to think about this,
in more abstract terms,
is that the ledger represents some state
(accounts hold some assets),
and the contracts define allowed state transitions
(which movement of assets are allowed).
It is up to the nodes to send state transition requests to the network,
and the validators use the contracts to validate those transitions.

Run the demo:

```bash
sudo -u algorand python3 deploy-contract-1.py /var/lib/algorand/net1/Primary
```

## Terminology

- Algorand protocol:
  protocol which can be used to run a blockchain based distributed ledger.
  It is based on an idea similar to Practical Byzantine Fault Tolerance
  with proof-of-stake.
  It offers block finality in seconds,
  as well as very large transaction throughput.

- Algorand Foundation:
  organization which created the Algorand protocol,
  built the reference implementation,
  and is currently in charge of the future development of Algorand.

- Algorand package:
  packaged distribution of the reference algorand implementation,
  distributed by the Algorand Foundation.

- Algo:
  the native coin at the heart of the Algorand network.
  It is used for staking and to fund future development.

- Ledger:
  the state of the (distributed) network,
  tracking association of various stateful quantities (e.g. coins) to accounts,
  and logic (contracts) used to evolve the state.

- Node:
  machine running an implementation of the Alogrand protocol,
  and interacting with a network of nodes to secure and update the ledger.

- Network:
  collection of nodes following the same protocol,
  and having synchronized states.
  There are 3 official public networks in the Algorand ecosystem:
  the main net, the test net and the beta net.
  Each runs variations of the protocol with a different genesis block.

- Account:
  address in the ledger to which state can be associated.

- Address:
  representation of a public cryptographic key.

- Private key:
  represetation of a public / private cryptographic key pair.

- Passphrase:
  human readable representation of a private key.

- Mnenomic:
  used interchangeably with "passphrase".

# An Algorand Tutorial

This is part tutorial, part exploration of the Alogrand developer experience.
This code base started out with the objective:
learn enough Algorand tooling and APIs to write a smart contract with voting mechanics,
and execute it on a ledger.

A very quick foreword on Algorand for the uninitiated:
Algorand is a pure proof-of-stake blockchain with deployed smart contract functionality.
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

## Key defintions

Here are a few definitions to help read this document:

- `algod`:
  the Alogrand daemon which runs a node on a nework.
- `node`:
  a machine participating in the Algorand protocol,
  and communicating with other nodes on a network.
  The nodes keeps a copy of the ledger synchronized with the network,
  and can propose modifications to the ledger (transactions).
- `network`:
  a group of nodes participating in a version of the Algorand protocol with a common genesis block.
  The Algorand tools keep track of three networks: MainNet, TestNet and BetaNet.
  MainNet and TestNet follow the same protocol,
  but have different genesis blocks and thus different histories.
  BetaNet follows a different protocol version.
- `kmd`:
  the key manager daemon which manages account information,
  including private keys,
  and relay that information to a node.
- `account`:
  a public / public key pair which can be used in the Algorand protocol.
  Accounts on the ledger can:
  track ownership of assets,
  track state of smart contracts,
  and authorize transactions.

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

In this tutorial, you will configure and run a node locally,
and have it connect to your own private network.
The advantages are that your work is fully self-contained,
you can inspect and reason about all the ledger data,
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
the node is being told to run with the data created by `goal` when the private network was built,
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

More:
<https://developer.algorand.org/docs/reference/teal/specification/>

### Smart signature (stateless)

A TEAL program compiled in "signature" mode is stateless.
Its inputs are the transaction fields,
some globl fields,
and optional invokation arguments.
It signs or does not sign a transaction depending on the result of its logic.

Consider that the ledger represents some state
(accounts hold some assets),
and a contract defines some allowed state transitions
(which movement of assets are allowed).
A node sends a request for some state transition
(a transaction),
and the validators use the contract to validate the transition.

A contract can be used as a "contract account" or a "delegate signature".
More: <https://developer.algorand.org/docs/features/asc1/stateless/modes/>

If assets are sent to the contract,
the contract can then "spend" those assets:
transactions can be submitted which move assets from the contract address to another address.
The network will confirm such transactions if and only if the contract logic evalues to true.

Alternativeluy, an account can sign a contract.
The contract then becomes a delegate of that account.
Transactions can be submitted to the network without the sender signature,
but with the contract in its stead.
If the contract evalutes to true on the transaction,
the network confirms it.

Run the demo:

```bash
sudo -u algorand python3 contract-periodic.py /var/lib/algorand/net1/Primary
sudo -u algorand python3 contract-periodic.py /var/lib/algorand/net1/Primary --use_delegate
```

### Smart contract (stateful)

A TEAL program compiled in "application" mode is stateful.
It is similar to a stateless contract in that it is invoked by a transaction,
and it evalutes some logic which returns true or false.
However, a statelss contract:

- has some state which is tracked on the ledger
- does not approve a sepending transaction,
  but rather approves arbitrary state changes to its own state

Both are evaluating whether or not some state change should be applied.
In a stateless contract,
the state change is defined by the transaction (e.g. a payment) and is limited to moving assets on the ledger.
In a stateful contract,
the state change is an arbitrary manipulation of the contract state as defined in its program.

The contract has access to global state (stored in the creating account),
and local state (stored in each account which has opted into the contract).

In a stateful transaction,
the transaction type determines the change of state to take place upon returning true
(e.g. a payment).
By contrast, in a stateless transaction,
the transaction type indicates which interaction the calling account should have with the contract,
after the contract finishes executing its program.

Here are the transactions types:

- `NoOp`: no further state changes are made to the ledger beyond the program's execution.
- `OptIn`: contract state should be initialized in the calling account
  (only relevant for contracts which use local storage).
- `DeleteApplication`: contract program and state should be removed from the ledger.
- `UpdateApplication`: contract program should be updated.
- `CloseOut`: contract state should be removed from the calling account.
- `ClearState`: contract state *will* be removed from the calling account.

In general,
each transaction will trigger the contract's program to execute,
and will either take effect or not depending on its return value.
If the program returns false,
the state changes made during the program execution are not confirmed by the network.
However,
the `ClearState` transaction will take effect no matter the return code.

NOTE: "program" here is used to describe the logic tied to the contract.
But in fact there are two separate programs tied to a stateful contract:
the `ApprovalProgram` and the `ClearStateProgram`.
The latter is executed when the transaction is of type `ClearState`.

NOTE: data has been described generically here, but in reality is constrained by size limits.
These details can be found at:
<https://developer.algorand.org/docs/reference/parameter_tables/>

### Voting treasury demo

The demo is intended to create a voting treasury:
an account which can be funded by multiple users,
and whose funds can be spent by users upon being voted-in as treasurer.

Requirements for the demo:

- An account can become a member by funding the contract.
- A member can nomiate themselves as treasuer and propose a budget (amount).
- A nomination voting period is triggered.
- During a nomination voting period,
  no other nominations are allowed.
- During a nomination voting period,
  members can cast a vote (weighted by their contribution to the funds).
- The vote succeeds if it the sum of voted weights exceeds some threshold.
- After a successful vote,
  new nominations are not accepted for some duration (the mandate).
- After a failed vote,
  the nominee cannot nominate themselves for some duration (cooldown).
- The treasurer can spend funds up to the proposed budget.

Lacking functionality:

- Voting on new memberships
- Voting on contract closure
- Unilateral contact exits
- Initial configuration (e.g. pre-approved accounts, min funds to start)

Approach:

- A stateful contract will track:
  - phase: accepting nomination, accepting votes
  - current treasurer
  - current budget
  - nominated treasurer
  - proposed budget
  - tallied votes for nomiation
- A stateless contract will hold the funds.
- The stateless contract will approve transactions from the treasurer,
  up to the current budget.
- Communication between the two contracts will be done in the scratch space.
- To spend,
  the treasurer will submit a group of:
  a transaction to the stateful contract seeking approval,
  the payment transaction from the statless contract.
- The stateful contract will verify that the treasurer is allowed to spend the amount in the payment transaction,
  and write the result in the scratch space.
- The stateless contract will ensure that it is the 2nd in a group of two transactions,
  the first being the stateful contract,
  and will read the approval from the scratch space.

The communcation could also be done using an ASA,
but this introduces many other state transitions
(all standard functions related to ASAs).
While these can be managed,
it would appear to increase the risk of misconfiguration.

## Terminology

- Algorand protocol:
  protocol which can be used to run a blockchain based distributed ledger.
  It is based on an idea similar to Byzantine agreement stake to elect nodes.
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

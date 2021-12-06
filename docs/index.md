---
layout: page
title: Preface
---

This tutorial covers the development of Algorand stateful apps (smart contracts) in a Python environment.
It was developed in tandem with the [`pyteal-utils`](https://github.com/gmcgoldr/pyteal-utils) package and will frequently refer to it.
The source code shown in this tutorial can be found at <https://github.com/gmcgoldr/algorand-tut>.

The tutorial will guide you through:

1. [Configuration]({{ site.baseurl }}{% link configuration.md %}):
   setting up a development environment
2. [Transactions]({{ site.baseurl }}{% link transactions.md %}):
   interfacing with a node using [`py-algorand-sdk`](https://github.com/algorand/py-algorand-sdk),
3. [Applications]({{ site.baseurl }}{% link applications.md %}):
   building an application (smart contract) using [`pyteal`](https://github.com/algorand/pyteal),
4. [Testing]({{ site.baseurl }}{% link testing.md %}):
   testing the application logic.

This preface is a non-technical overview of blockchain and smart contract concepts,
meant to help motivate the contents of the tutorial.
You can skip ahead to the [configuration]({{ site.baseurl }}{% link configuration.md %}) section to get right into the code.

## Algorand

Algorand is a proof-of-stake blockchain with smart contract functionality.

As a developer, it is attractive because the technology so far is proving robust,
its smart contract language avoids pitfalls discovered in precursor technologies,
and it is operationally simple enough that a node can be run on commodity hardware.

As a blockchain technology, it also demonstrates some good qualities:

- transaction finality is less than 5 seconds
- thousands of transactions per second
- very low transaction fees
- decentralization
  - the [community votes](https://governance.algorand.foundation) on protocol governance
  - the block rewards are distributed to the entire network not just the validators
  - the barrier to entry for running a node is very low

The protocol is so efficient that it can run on a [Raspberry Pi](https://developer.algorand.org/tutorials/development-on-algorand-using-raspberry-pi-part-1/).
This helps with decentralization, as nearly anyone can run a node.
But it also makes Algorand very power efficient.
As of writing, using the numbers available on the [dashboard](https://metrics.algorand.org/),
and assuming about 10 W of energy per node
(e.g. when sharing resources in a data center, or when running on a Raspberry Pi)
then the entire validation network is currently consuming about 15 kW of energy.
That's roughly equivalent to 30 gaming computers.

### Blockchain

{::nomarkdown}<center>{%- include svgs/blockchain.svg -%}</center>{:/}

Blockchain technologies are protocols which facilitate distributed computing.
They allow many nodes in a network to agree on some shared state (a ledger),
under some allowed state transition rules.
The rules could be part of the protocol (e.g. UTXO),
or could be programs stored on the ledger (i.e. smart contracts).

Proof-of-work technologies rely on proving that some computational work has been done,
to give priority to whichever state which has more backing (in the form of work).
This is used to decide which fork of the ledger is the correct one,
and can be seen as a way to order transactions.

Proof-of-stake is a bit of a misnomer as there's isn't much proving happening.
Instead, the stake is used to weight participation in some Byzantine fault tolerant protocol.
In the case of Algorand the protocol doesn't fork.
This means that the ordering problem is addressed without using proof-of-work.

Blockchains can offer some novel features:

- Transparent: anyone can verify the current state and rules which govern the state
- Consistent: state is updated and deleted following known rules
- Equitable: all participants are subject to the same rules
- Permissionless: no entity can deny another from participating

Cryptocurrency is probably the most famous use case for such a network.
In the case of Bitcoin, the network was designed for exactly this purpose,
and the protocol enforce the rules of currency:
a coin can be owned by a single entity at a time,
and only the owner of a coin can approve its transfer.

Here is a somewhat arbitrary comparison a blockchain versus a centralized database:

| Blockchain | Centralized |
| - |
| full state is known | some information can be withheld |
| data updates follow known rules | data can be tampered with |
| rules apply equally | favoritism possible |
| access not subject to change | access can be revoked and denied |

And there are some caveats to consider:
not all blockchains are truly decentralized,
sufficiently complex rules can become opaque,
rules can be discriminatory,
a contract which can be arbitrarily updated is arbitrary,
a contract which can be arbitrarily deleted is ephemeral
etc.

### Beyond financial applications

A good way to think of  smart contracts is in terms of transactions.
A smart contract defines some state which is recorded on the ledger,
and some transactions (state changes) which are permissible under the rules of the contract.

The technology gets more interesting when thinking of transactions in the broad sense of the word,
not in the strictly financial sense.

Consider tracking identity in the real world.
Currently, a person's identity is largely established by credentials issued by their government.
But a person can be denied credentials (permissioned),
their credentials can be invalidated by a hostile issuer (inconsistent),
and their credentials can be used to discriminate based on arbitrary status (inequitable).

This can, to some extent, be resolved by transacting in credibility on a blockchain.
Someone can create a transaction in which they vouch for someone else's credentials.
The graph of such vouches can be used to asses a person's credibility,
in a permissionless, transparent and consistent manner.

{::nomarkdown}<center>{%- include svgs/person-graph.svg -%}</center>{:/}

In the above example,
Alice directly trusts Bob and Charlie.
Alice can probably also trust Dave,
given that she knows two people vouching for Dave.
But Alice might be suspicious of Grace,
because she knows only one person vouching for Grace.
Which is all well and good as Grace, Erin and Frank are bots colluding to give the impression of credibility.
And fooling Charlie isn't enough to establish credibility in the eyes of Alice.

This tutorial will cover the steps required to build such a smart contract.

---
layout: page
title: Introduction
---

This tutorial covers the development of Algorand stateful apps (smart contracts) in a Python environment.
This introduction provides a non-technical overview of blockchain and smart contract concepts,
to help situate Algorand in the field.

The tutorial source code shown can be found at <https://github.com/gmcgoldr/algorand-tut>.
You can skip ahead to the [configuration]({{ site.baseurl }}{% link configuration.md %}) section to get into the code.

## Algorand

Algorand is a proof-of-stake blockchain with smart contract functionality.

As a developer, it is attractive because the technology so far is proving robust,
its smart contract infrastructure avoids many
[pitfalls](https://consensys.github.io/smart-contract-best-practices/known_attacks/) discovered in precursor technologies,
and it is operationally simple enough that a full node can be run on a
[Raspberry Pi](https://developer.algorand.org/tutorials/development-on-algorand-using-raspberry-pi-part-1/).

As a blockchain technology, it also demonstrates some good qualities:

- transaction finality is less than 5 seconds
- thousands of transactions per second
- very low transaction fees
- decentralization
  - the [community votes](https://governance.algorand.foundation) on protocol governance
  - the block rewards are distributed to the entire network not just the validators
  - the barrier to entry for running a node is very low

The protocol's efficiency,
while primarily addressing decentralization and throughput,
also makes the network very power efficient.
As of writing, using the numbers available on the [dashboard](https://metrics.algorand.org/),
and assuming about 10 W of energy per node
(e.g. when sharing resources in a [data center](https://medium.com/teads-engineering/estimating-aws-ec2-instances-power-consumption-c9745e347959),
or when running on a Raspberry Pi)
the entire validation network could be consuming as little as 15 kW of energy.
That's less power consumption than two typical American households.

### Blockchain

{::nomarkdown}<center>{%- include svgs/blockchain.svg -%}</center>{:/}

Blockchain technologies are protocols which implement some form of distributed computing.
They allow many nodes in a network to agree on some shared state (e.g. ledger),
under some allowed set of transition rules.
The rules could be part of the protocol (e.g. UTXO),
or could be programs stored on the ledger (e.g. smart contracts).

For typical proof-of-work (PoW) protocols,
proof that some computational work has been done is used to randomly select a leader node,
which will send a new block of transactions to the network.
Two (or more) nodes could propose different blocks at the same time,
resulting in a fork of the ledger.
The nodes agree that whichever version of the ledger has the most backing (computation work) is accepted as the correct one.

> A fork occurs when, after some state X is confirmed,
two new states Y and Y' are proposed which are both compatible with X,
but are incompatible with one-another.
Double-spending is an example of this situation:
in state X, Alice has 1 coin.
Alice proposes to pay Bob her 1 coin, resulting in state Y.
At the same time, she proposes to pays Charlie her 1 coin, resulting in state Y'.
The network must choose to confirm Y and discard Y', or vice versa.

For typical proof-of-stake (PoS) protocols,
each node's stake is used to weight participation in some Byzantine fault tolerant protocol.
Ethereum's Casper protocol was heavily inspired by Bitcoin's leader selection.
But the protocol requires many amendments in lieu of the PoW-based fork resolution.
More recent PoS blockchains tend to be built on protocols which have little in common with Bitcoin.
The Algorand protocol uses random sortition to select a leader in a manner which doesn't introduce forks.

In effect,
a blockchain allows many nodes to transact on a decentralized database,
without having to trust one-another or a third party.
While centralized databases are simpler and more efficient to operate,
blockchains can be said to be:

- Transparent: anyone can verify the current state and rules which govern the state;
- Consistent: state is updated and deleted following known rules;
- Fair: all participants are subject to the same rules;
- Permissionless: no entity can deny another from participating.

| Blockchain | Centralized |
| - |
| rules are known | rules can change unexpectedly |
| updates follow known rules | tampering possible |
| rules apply equally | favoritism possible |
| access follows known rules | access can be revoked unexpectedly |

Given absolute trust in the organization operating a centralized database,
then these issues may seem inconsequential.
But the risk of corruption increase as the value of the service entrusted to the organization increases.

When the risk of corruption becomes significant,
either because trust is difficult or because the value of the service is large,
then the guarantees offered by a blockchain become more valuable.

### Beyond financial applications

A good way to think of smart contracts is in terms of transactions.
A smart contract defines some state which is recorded on the ledger,
and some transactions (state changes) which are permissible under the rules of the contract.

The technology gets more interesting when thinking of transactions in the broad sense of the word,
not in the strictly financial sense.

Consider the issue of personal identity.
Currently, identity is largely established by credentials issued by some government.
But a person can be denied credentials (permissioned),
their credentials can be invalidated (inconsistent),
and their credentials can be used to discriminate based on arbitrary status (unfair).

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

Next in the tutorial: [configuration]({{ site.baseurl }}{% link configuration.md %}).

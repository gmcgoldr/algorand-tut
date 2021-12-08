---
layout: page
title: Introduction
---

This tutorial covers the development of Algorand stateful apps (smart contracts) in a Python environment.
It was developed in tandem with the [`algo-app-dev`](https://github.com/gmcgoldr/algo-app-dev) package and will frequently refer to it.
The source code shown in this tutorial can be found at <https://github.com/gmcgoldr/algorand-tut>.

The tutorial will guide you through:

1. [Configuration]({{ site.baseurl }}{% link configuration.md %}):
   setting up a development environment
2. [Transactions]({{ site.baseurl }}{% link transactions.md %}):
   building and sending a transaction to the network.
3. [Applications]({{ site.baseurl }}{% link applications.md %}):
   building an application (smart contract) and transacting with it.
4. [Testing]({{ site.baseurl }}{% link testing.md %}):
   testing the application logic.

This introduction is a non-technical overview of blockchain and smart contract concepts,
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
(e.g. when sharing resources in a [data center](https://medium.com/teads-engineering/estimating-aws-ec2-instances-power-consumption-c9745e347959),
or when running on a Raspberry Pi)
then the entire validation network is currently consuming about 15 kW of energy.
That's roughly equivalent to 30 gaming computers.

### Blockchain

{::nomarkdown}<center>{%- include svgs/blockchain.svg -%}</center>{:/}

Blockchain technologies are protocols which facilitate distributed computing.
They allow many nodes in a network to agree on some shared state (e.g. ledger),
under some allowed state transition rules.
The rules could be part of the protocol (e.g. UTXO),
or could be programs stored on the ledger (e.g. smart contracts).

Proof-of-work technologies rely on proving that some computational work has been done,
to give priority to whichever state which has the most backing (in the form of work).
This is used to decide which fork of the ledger is the correct one,
and can be seen as a way to order transactions.

> A fork occurs when, after some state s1 is confirmed,
two new states s2 and s3 are proposed which are both compatible with s1,
but are incompatible with one-another.
Double-spending is a classic example of this situation:
in state s1, Alice has 1 coin.
Alice announces a transaction in which she pays Bob, resulting in s2.
At the same time, she announces a transaction in which she pays Charlie, resulting in state s3.
The network must choose to continue either from s2 and discard s3, or vice versa.

Proof-of-stake is a bit of a misnomer as there isn't much proving happening.
Instead, the stake is used to weight participation in some Byzantine fault tolerant protocol.
In the case of Algorand the protocol doesn't fork.
This means that the ordering problem is addressed without using proof-of-work.

Cryptocurrency is probably the most famous use case for such a network.
In the case of Bitcoin, the network was designed for exactly this purpose,
and the protocol enforces the rules of currency:
a coin can be owned by a single entity at a time,
and only the owner of a coin can approve its transfer.

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

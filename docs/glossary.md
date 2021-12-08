---
layout: page
title: Glossary
---

- **Algorand protocol**:
  protocol which can be used to run a blockchain based distributed ledger.
  It performs full Byzantine agreement at each block,
  allowing for block finality (no forking) in seconds.
  Participation in consensus is weighted by stake,
  making this a proo-of-stake blockchain.

- **Algorand Inc**:
  company which created the Algorand protocol,
  built the reference implementation,
  and is researching future improvements.

- **Algorand Foundation**:
  non profit which handles protocol governance (upgrades), token circulation, and funding open source initiatives.

- **Algorand package**:
  packaged distribution of the reference algorand implementation,
  distributed by the Algorand Foundation.

- **Algo**:
  the native coin at the heart of the Algorand network.
  It is used for staking, voting on governances (upgrades), and to fund future development.

- **Ledger**:
  the state of the (distributed) network,
  tracking association of various stateful quantities (e.g. coins) to accounts,
  and logic (contracts) which define allowed state transitions.

- **Node**:
  machine running an implementation of the Alogrand protocol,
  and interacting with a network of nodes to secure and update the ledger.

- **Network**:
  collection of nodes following the same protocol,
  and having synchronized states.
  There are 3 official public networks in the Algorand ecosystem:
  the main net, the test net and the beta net.
  Each runs variations of the protocol with a different genesis block.

- **Account**:
  address in the ledger to which state can be associated.

- **Address**:
  representation of a public cryptographic key.

- **Private key**:
  represetation of a public / private cryptographic key pair.

- **Passphrase**:
  human readable representation of a private key.

- **Mnenomic**:
  used interchangeably with "passphrase".

- **Smart contract**:
  some logic stored on the ledger,
  which is used to specify rules about which ledger state transitions are allowed.

- **Application** (app, dApp):
  service with some state and rules stored on the ledger.
  Typically, the application can have a front-end distributed to users,
  a back-end consisting of smart-contracts,
  and further back-end functionality deployed in some kind of data-center.

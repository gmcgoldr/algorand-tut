---
layout: page
title: Transactions
---

The following explains how to use the Python SDK to create, execute and inspect transactions.
The associated code can be found in `demo-transfer.py`.
The `aad` module here refers to `algoappdev`,
as imported in `demo-transfer.py`.

## Running the code

```bash
# start the algod and kmd daemons
sudo -u algorand aad-run-node private_dev start
# run the demo
sudo -u algorand ./demo-transfer.py /var/lib/algorand/nets/private_dev/Primary
# stop the daemons to cleanup background processes
sudo -u algorand aad-run-node private_dev stop
```

## Daemon clients

You first need to establish a connection to the `algod` daemon,
to interact with the network,
and to the `kmd` daemon,
to access the funds in the genesis account.

```python
algod_client = aad.clients.build_algod_local_client(node_data_dir)
kmd_client = aad.clients.build_kmd_local_client(node_data_dir)
```

The build local client functions simply lookup the client network address and access token in the node data directory,
and construct the `algosdk.v2client.algod.AlgodClient` and `algosdk.kmd.KMDClient` objects.

## Using the Key Management Daemon

In normal operations,
your account private keys will be managed by a wallet and accessed with `kmd`.
The following code snippet looks up a wallet in `kmd`,
and then makes a request to `kmd` to get the first account's address in the wallet.

```python
wallet = ag.wallet.Wallet(wallet_name, password, kmd_client)
sender = wallet.list_keys()[0]
```

Then, to sign a transaction:

```python
signed_txn = wallet.sign_transaction(txn)
```

In this demo,
the `KMDClient` is used only to interact with the account added to the default wallet at genesis.
A new wallet can be created with `KMDClient.create_wallet`,
and once a wallet is created many addresses and keys can be generated within it.
See: <https://developer.algorand.org/docs/get-details/accounts/create/>.

## Using a standalone account

It is also possible to generate a standalone account.
In fact, an account is just the 32-byte public key in an Ed25519 public / private key pair.
So, in theory, any implementation of Ed25519 can "create" an account.

But be very careful: if you provide an address to the Algorand network for which there is no known private key,
then any assets sent to that address are lost forever.

To generate a standalone account:

```python
private_key, address = ag.account.generate_account()
```

This generates the private key, and algorand address, as per
<https://developer.algorand.org/docs/get-details/accounts/>.

Keep in mind that there are security considerations to take into account when dealing with private keys.
Using a wallet managed by `kmd` offers some security against common issues that arise when passing private keys around.
Consider, for example, passing a private key to the wrong endpoint and having it logged in plain text.

## Accessing information about an account

Account information can be queried with the `AlgodClient.account_info` method.
The resulting dictionary is an encoding of the following object:
<https://developer.algorand.org/docs/rest-apis/algod/v2/#account>.

NOTE: serialized objects returned by the daemon APIs are found at
<https://developer.algorand.org/docs/rest-apis/algod/v2/#definitions>.

## Building a payment transaction

Fundamentally, a transaction is a request sent to the Algorand network,
requesting some state change.
The network handles a few different transaction types:
payments, validation participation, standard asset manipulation, and smart contract manipulation.
Learn more here: <https://developer.algorand.org/docs/get-details/transactions/>.

Many arguments are passed to a transaction to tell the network exactly how the state change is to proceed.
These parameters are documented here: <https://developer.algorand.org/docs/get-details/transactions/transactions/>.

The following snippet of code creates a payment transaction,
with default values used for most of the transaction parameters:

```python
params = algod_client.suggested_params()
params.fee = 0
txn = PaymentTxn(
    sender=from_address,
    sp=params,
    receiver=to_address,
    amt=ag.util.algos_to_microalgos(1),
    note=note,
)
```

The Python SDK contains objects which help configure the various transaction types
Here `algosdk.future.transaction.PaymentTxn` is used to create a payment.
Some of the parameters are self-evident:
`sender` is the address of the sender,
`receiver` is the address of the receiver,
`amt` is the amount of *microAlgos* to send.
The `note` parameter is used to attach up to 1 KB of raw data (byte slice) to the transaction.

More arguments can be passed,
such as the lease, rekey address, and close out address.
These topics aren't covered in this tutorial.

### Suggested parameters

The `sp` parameter, which stands for suggested parameters,
is an object which contains information about how the transaction should be handled by the network.
The `AlgodClient.suggested_params` method builds such an object,
and populates it with sensible defaults based on the current state of the network.

The object describes:

- which network to interact with
  (it specifies the genesis and protocol it whishes to interact with)
- the fees which the sender will pay
- some duration over which the transaction is valid,
  and after which if the transaction isn't executed then it is dropped from the network

The `fee` and `flat_fee` members are used to specify the fees paid to get the transaction confirmed.
The actual fee is calculated as follows where `min_fee` is the minimum transaction fee,
and `num_bytes` is the number of bytes for the packed signed transaction.
The last row follows from the previous,
and is added here just for clarity.

| fee | flat | actual fee |
| - |
| `x` | `True` | `x` |
| `x` | `False` | `max(min_fee, x * num_bytes)` |
| `0` | `False` | `min_fee` |

The `first` and `last` members specify a range of rounds in which the transaction must be confirmed,
otherwise it is dropped.
The round is a counter which increases each time a block is committed.
In its current configuration,
the network commits a block every `4.5` seconds on average,
but this will probably be reduced with network upgrades.

Calling `AlgodClient.suggested_params` will default to a non-flat fee,
with `fee` set to the network minimum fee.
This means the transaction fee will scale with the transaction size,
and while the network is not congested you can either set `flat_fee` to `True`,
or just set `fee` to `0` to pay strictly the minimum network fee.
The `first` round will be set to the last committed round,
and the `last` round will be offset by the maximum transaction life.

The minimum transaction fee,
and maximum transaction life (number of valid rounds) can be found here:
<https://developer.algorand.org/docs/get-details/parameter_tables/>.

## Sending a transaction

A transaction must be signed before it can be sent to the network.
A transaction can be signed by the appropriate private key in a wallet if the sender is an account in the wallet:

```python
signed_txn = wallet.sign_transaction(txn)
```

Or directly using the private key:

```python
signed_txn = txn.sign(private_key)
```

The resulting signed transaction is a `future.transaction.SignedTransaction` object,
which wraps the original transaction alongside the signature data.

The transaction is sent using the `AlgodClient`:

```python
txid = algod_client.send_transaction(signed_txn)
```

At this point, the transaction is in the network,
and is identified by its id `txid` (base64 encoded transaction hash).
It will remain in the network until it can be included in a block,
at which point it will be confirmed.

Waiting for a transaction to be confirmed is a common operation,
as seen in this snippet:

```python
txn_info = aad.transactions.get_confirmed_transaction(
    algod_client,
    txid,
    wait_rounds
)
```

The `AlgodClient.status_after_block` method is used to block the thread until the client reports a new block.
This can be used in a loop to query the transaction information at each block until it is seen to be confirmed.
The transaction information can be queried with `AlgodClient.pending_transaction_info`. The resulting object's schema can be found at:
<https://developer.algorand.org/docs/rest-apis/algod/v2/#pendingtransactionresponse>.

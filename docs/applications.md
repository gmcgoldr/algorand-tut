---
layout: page
title: Applications
---

The following explains how to create and call an application.
The associated code can be found in `demo-app.py`.
Note that in the following code snippets,
PyTeal and algo-app-dev are imported into the namespace
(i.e. `from pyteal import *` and `from algoappdev import *` are assumed).

The functionality in stateful applications (apps) is executed with an *app call* transaction.
This is a transaction with the `TxType` field set to the `appl` variant.
Other transaction types such as payments, asset minting etc. are not discussed here.

Application call transactions can be constructed with
`py-algorand-sdk` in as follows:

```python
future.transaction.Transaction(txn_type=constants.appcall_txn)
```

There are also a variety of `future.transaction.Application...` objects which are derived from `Transaction`,
and which set `txn_type=constants.appcall_txn` during construction.

## Application context

An app is comprised of some state,
and some rules which specify how the state can be affected by app call transactions.
It is useful to think of the application as a function,
and the transactions as calling that function,
where the transaction is supplying arguments to the call.

There are many fields (arguments) which can be accessed by an app.
The full list can be found at:
<https://developer.algorand.org/docs/get-details/transactions/transactions/>.

Here is an overview of how the various app call fields relate to one-another,
taken from
<https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/#smart-contract-arrays>:

![Application Context](https://developer.algorand.org/docs/imgs/stateful-2.png)

The app call as a function might be described as follows (some fields are omitted):

```python
call_app(
    # scope: global
    creator_address: Bytes,
    current_application_id: Int,
    latest_timestamp: Int,
    ...
    # scope: transaction i
    sender_i: Bytes,
    on_completion_i: Int,
    application_args_i_idx_j: Bytes,
    applications_i_idx_j: Int,
    assets_i_idx_j: Int,
    ...
    # scope: asset i
    asset_i_creator: Bytes,
    asset_i_total: Int,
    ...
    # scope: asset i, account j
    asset_i_account_j_balance: Int,
    asset_i_account_j_frozen: Int,
    # scope: app i (global storage)
    app_i_key_k: Union[Bytes, Int],
    # scope: app i, account j (local storage)
    app_i_account_j_key_k: Union[Bytes, Int],
)
```

The global scope fields can be accessed with expressions: `Global.field_name()`.

The transaction fields can be accessed with expressions: `Gtxn[i].field_name()`.
And for those fields that are in an array (`_idx` suffix above),
they are accessed by indexing into an array: `Gtxn[i].array_name[j]`.

The app state can be accessed with the methods:

- `App.globalGet(key)`
- `App.localGet(address, key)`
- `App.globalGetEx(id, key)`
- `App.localGetEx(address, id, key)`

`key` is the key for the state value to retrieve;
`id` is the id of the app in which to lookup the key, or the index of an app in the app array;
`address` is the address of the local storage in which to lookup the key, or an index in the account array.

The first two expressions return the state value and work only for the current app.
The last two expressions return an object `MaybeValue` which is itself an expression.
When executed, it constructs two values: whether or not the key was found, and its value
(or default value if not found).
Then, those values can be accessed with expressions: `maybe.value()`, `maybe.hasValue()`.

In the previous example, `app_1_account_2_key_A` would be accessed by:
`App.localGetEx(Txn.accounts[2], Txn.applications[1], Bytes("A"))`.

Note the following equivalences
(keeping in mind that `GetEx` calls must first be evaluated,
and that `GetEx` calls with app ID `0` will use the current application which is at index `0` in the app array):

| `Txn` | `Gtxn[0]` |
| `Txn.sender()` | `Txn.accounts[0]` |
| `Global.current_application_id()` | `Txn.applications[0]` |
| `App.globalGet(key)` | `App.globalGetEx(0, key).value()` |
| `App.localGet(addr, key)` | `App.localGetEx(addr, 0, key).value()` |

## Application logic

An application program is a PyTeal expression,
which returns either zero, or a non-zero value.
A non-zero value indicates that the transaction is successful:
changes made to the app's state during the program execution are committed.
A zero value indicates that the transaction is rejected:
the state is left unchanged.

A stateful app on the Algorand chain consists of two programs:
the approval program, and the clear state program.

{::nomarkdown}<center>{%- include svgs/programs.svg -%}</center>{:/}

The clear state program is executed when a app call transaction is sent with the `OnComplete` code: `ClearState`.
This transaction will always remove the local app state from the caller's account,
regardless of return value.
Any other state changes (to the global app state) may or may not be committed,
depending on the program's return value.
All other app call transactions will execute the approval program.

## Application builder

There are two utility classes in `algo-app-dev` which help in the creation of apps:
The `State` class and `AppBuilder` class.
This section covers how to use these to:
define the state of an app,
and define the app's logic.

### State

The application can persist state globally and locally (per account).
Up to 64 values can be stored in the global state,
and up to 16 values can be store in the local state.
Each accounts which opts into the app can then store its own instance of the local state.

A `State` object is used to describe the key value pairs making up the state of a contract.
It is initialized with a list of `KeyInfo` objects,
each specifying the key,
the type of its associated value,
and possibly a default value.

A `State` object is used to:

- build expressions to set and get a state value
- build an expression to set default values (constructor)
- build the app schema which defines how much space the app can use

The `StateGlobalExternal` subclass of `State` is used to describe the global state for an external app
(i.e. any app whose id is in the `Txn.applications` array).
It can get values, but cannot set them as external apps read-only.

The `StateGlobal` subclass of `StateGlobalExternal` is used to describe the global state for the current app.
It adds the ability to set values in the state.
And it adds a get method which directly returns a value,
instead of returning a `MaybeValue`.

The equivalent local classes are: `StateLocalExternal` and `StateLocal`.

In this demo application,
each account has a name associated with it (the credential),
and up to 8 accounts can vouch for that credential.
The local storage is comprised of the name, and 8 voucher addresses.

TEAL stack values (and consequently state values) are either of type `Bytes` or `Int`.
The `Bytes` type represents a byte slice, and can be used to represent arbitrary binary data.
Strings and addresses are encoded as byte slices.
The `Int` type represents an unsigned 64-bit integer.

```python
# the state consists of 8 indices each for a voucher address
MAX_VOUCHERS = 8
state = apps.StateLocal(
    [apps.State.KeyInfo(key="name", type=Bytes)]
    + [
        apps.State.KeyInfo(key=f"voucher_{i}", type=Bytes)
        for i in range(MAX_VOUCHERS)
    ]
)
```

### Logic branches

When using the `AppBuilder` class,
the resulting approval program's logic contains the following branches:

| Condition | Result |
| - |
| `Txn.application_id() == Int(0)` | Initialize the state |
| `OnComplete == DeleteApplication` | Delete the state and programs |
| `OnComplete == UpdateApplication` | Update the programs |
| `OnComplete == OptIn` | Initialize the local state |
| `OnComplete == CloseOut` | Delete the local state |
| `OnComplete == NoOp` <br/> `Txn.application_args[0] == Bytes(name)` | Call the invocation with `name` |
| `OnComplete == NoOp` | Call the default invocation |

Exactly one branch will execute.
Branches can be disabled by having them return zero.

The creation branch is invoked when the app ID is zero,
which happens only when a call is made to an app not yet on the chain.

A `NoOp` call with an argument at index 0 which matches an invocation name will invoke that branch.
A `NoOp` call without no argument at index 0,
or an argument which doesn't match any invocation name,
will invoke the default invocation branch.

In this demo application, the default app builder behavior is used:
opt-in is allowed, but delete, update and close out are not allowed.
The close out branch would be used if there was some logic tied to a user leaving the contract.
But in this case,
their local state need simply be cleared,
which is achieved with the clear program.

Additionally, the following three branches are added:
setting the name (`set_name`),
vouching for an account (`vouch_for`),
and receiving a vouch (`vouch_from`).

Perhaps the most interesting aspect of this contract is the grouping of the `vouch_for` and `vouch_from` logic.
The voucher and vouchee must both agree for a vouch to succeed.
It shouldn't be possible for a random voucher to take up vouch spots in a vouchee's account.
And it shouldn't be possible for a vouchee to claim a voucher without their permission.

The solution is to make the logic of writing a new vouch conditional on two transactions in a group.

```python
# the previous txn in the group is that sent by the voucher
voucher_txn = Gtxn[Txn.group_index() - Int(1)]
# the 3rd argument of the vouchee txn is the index to write to
vouch_key = Txn.application_args[2]
# valid vouch keys
vouch_keys = [Bytes(f"voucher_{i}") for i in range(MAX_VOUCHERS)]

builder = apps.AppBuilder(
    invocations={
        # setting the name changes the credentials, and so must clear the
        # vouchers (i.e. the vouchers vouched for a name, so a new name
        # requires new vouches)
        "set_name": Seq(
            Seq(*[state.drop(f"voucher_{i}") for i in range(MAX_VOUCHERS)]),
            state.set("name", Txn.application_args[1]),
            Return(Int(1)),
        ),
        # always allow the voucher to send this invocation along with the
        # vouchee address
        "vouch_for": Return(Int(1)),
        # vouchee sends this invocation to write the vouch to local state
        "vouch_from": Seq(
            # ensure voucher is using this contract
            Assert(voucher_txn.application_id() == Global.current_application_id()),
            # ensure voucher is vouching
            Assert(voucher_txn.application_args[0] == Bytes("vouch_for")),
            # ensure voucher is vouching for vouchee
            Assert(voucher_txn.application_args[1] == Txn.sender()),
            # ensure vouchee is getting vouch from voucher
            Assert(Txn.application_args[1] == voucher_txn.sender()),
            # ensure setting a valid vouch key
            Assert(Or(*[vouch_key == k for k in vouch_keys])),
            # store the voucher's address in the given vouch index
            App.localPut(Txn.sender(), vouch_key, voucher_txn.sender()),
            Return(Int(1)),
        ),
    },
    local_state=state,
)
```

### Building the application

The `AppBuilder.create_txn` combines all the branches into the approval and clear state programs,
and builds the transaction required to publish the app on the chain.

```python
txn = app_builder.create_txn(
    algod_client, address, algod_client.suggested_params()
)
```

Here is what the application creation transaction looks like:

```python
ApplicationCreateTxn(
    # this will be the app creator
    sender=address,
    sp=params,
    # no state change requested in this transaction beyond app creation
    on_complete=OnComplete.NoOpOC.real,
    # the program to handle app state changes
    approval_program=compile_source(client, compile_expr(self.approval_expr())),
    # the program to run when an account forces an opt-out
    clear_program=compile_source(client, compile_expr(self.clear_expr())),
    # the amount of storage used by the app
    global_schema=self.global_schema(),
    local_schema=self.local_schema(),
)
```

The `approval_expr` and `clear_expr` methods return the PyTeal expressions which make up the approval and clear state programs.

The `compile_expr` function compiles a PyTeal expression to TEAL source code.
The `compile_source` function compiles PyTeal source code into the program binary.

```python
def compile_expr(expr: Expr) -> str:
    return compileTeal(
        expr,
        mode=Mode.Application,
        version=MAX_TEAL_VERSION,
    )

def compile_source(client: AlgodClient, source: str) -> bytes:
    result = client.compile(source)
    result = result["result"]
    return base64.b64decode(result)
```

The application's ID and address can be retrieved from the transaction result,
using the `AppMeta` class:

```python
app_meta = utils.AppMeta.from_result(
    transactions.get_confirmed_transaction(algod_client, txid, WAIT_ROUNDS)
)
```

## Interacting with the application

Interacting with the application involves sending transactions to the application.
Transacting is covered in the
[Transactions]({{ site.baseurl }}{% link transactions.md %}) section.
Following is a brief example.

Bob wants to let the network know that his name is Bob.
He will first opt-in to the app:

```python
txn = ApplicationOptInTxn(address_bob, algod_client.suggested_params(), app_id)
```

Then he will link his name to his account:

```python
txn = ApplicationNoOpTxn(
    address_bob,
    algod_client.suggested_params(),
    app_id,
    ["set_name", "Bob"],
)
```

Now he can ask Alice to vouch for him:

```python
txns = transactions.group_txns(
    ApplicationNoOpTxn(
        address_alice,
        algod_client.suggested_params(),
        app_id,
        # the address must be decoded to bytes from its base64 form
        ["vouch_for", decode_address(address_bob)],
    ),
    ApplicationNoOpTxn(
        address_bob,
        algod_client.suggested_params(),
        app.app_id,
        [
            "vouch_from",
            decode_address(address_alice),
            # Bob has 8 vouch indices to choose from, this is his first so
            # he puts it at index 0
            "voucher_0",
        ],
    ),
)
```

Finally he will send Alice's transaction to her, and have her sign it.
Then he can send the transactions to the network.

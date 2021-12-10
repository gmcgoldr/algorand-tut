---
layout: page
title: Applications
---

The following explains how to create and call an application.
The associated code can be found in `demo-app.py`.

The functionality in stateful applications (apps) is executed with an *app call* transaction.
This is a transaction with the `TxType` field set to the `appl` variant.
Other transaction types such as payments, asset minting etc. are not discussed here.

## Application context

A app is comprised of some state,
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
    application_args_i_index_j: Bytes,
    applications_i_index_j: Int,
    assets_i_index_j: Int,
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
And for those fields that are in an array (`_index_j` suffix above),
they are accessed by indexing into an array: `Gtxn[i].array_name[j]`.

The app state can be accessed with the methods:

- `App.globalGet(key)`
- `App.localGet(address, key)`
- `App.globalGetEx(id, key)`
- `App.localGetEx(address, id, key)`

`key` is the key for the state value to retrieve,
`id` is the id of the app in which to lookup the key,
`address` is the address of the local storage in which to lookup the key.

The first two expressions return the state value and work only for the current app.
The last two expressions return an object `MaybeValue` which is itself an expression.
When executed, it retrieves two values: whether or not the key was found, and its value
(or default value if not found).
Then, those values can be accessed with expressions: `maybe.value()`, `maybe.hasValue()`.

In the previous example, `app_1_account_2_key_A` would be accessed by:
`App.localGetEx(Txn.accounts[2], Txn.applications[1], Bytes("A"))`.

Note the following equivalences
(keeping in mind that `GetEx` calls must be evaluated):

| `Txn` | `Gtxn[0]` |
| `Txn.sender()` | `Txn.accounts[0]` |
| `Global.current_application_id()` | `Txn.applications[0]` |
| `App.globalGet(key)` | `App.globalGetEx(Txn.applications[0], key).value()` |
| `App.localGet(addr, key)` | `App.localGetEx(addr, Txn.applications[0], key).value()` |

## Application logic

An application program is a PyTeal expression,
which returns either zero, or a non-zero value.
A non-zero value indicates that the transaction is successful:
changes made to the app's state during the program execution are committed.
A zero value indicates that the transaction is rejected:
the state is left unchanged.

In that sense,
a transaction can be seen as request to effect some state change.
And the return value of the program called by the transaction indicates whether or not the state change is committed.

A stateful app on the Algorand network consists of two programs:
the approval program, and the clear state program.

{::nomarkdown}<center>{%- include svgs/programs.svg -%}</center>{:/}

The clear state program is executed when a app call transaction is sent with the special `OnComplete` code: `ClearState`.
This transaction will always remove the local app state from the caller's account,
regardless of return value.
Any other state changes (to the global app state) may or may not be committed,
depending on the program's return value.
All other app call transactions will execute the approval program.

## Application builder

There are two utility classes in `algo-app-dev` which help in the creation of apps.
The `AppBuilder` class,
and the `State` class and its derived classes.
This section covers how to use these to:
define the state of an application,
and define the app's logic.

### State

The application can persist state globally and locally (per account).
Up to 64 values can be stored in the global state,
and up to 16 values can be store in the local state.
Each accounts which opts into the app can then store its own instance of the local state.

A `State` object is used to describe the key-values making up the state of a contract.
It is initialized with a list of `KeyInfo` objects,
each specifying the key of a state value,
the type of the value,
and possibly a default value.
The key can be an integer, a string or bytes.

A `State` object is used to:

- access set / get a state value in the app logic
- build the app constructor which is run on opt-in
- build the app schema which defines how much space the app can use

A `StateGlobalExternal` subclass of `State` is used to describe the global state for an arbitrary app.
It has methods for getting and setting global state values.
A `StateGlobal` subclass of `StateGlobalExternal` adds members for getting and setting state in the current app.

The equivalent local classes are: `StateLocalExternal` and `StateLocal`.
`StateLocal` in this case gets and sets state in the current app for the transaction sender.

In this demo application,
each account can be vouched for by up to 8 accounts.
So the local storage is 8 byte slices (a byte slice can store an address).

```python
# the state consists of 8 indices each for a voucher address
MAX_VOUCHERS = 8
state = apps.StateLocal(
    [apps.State.KeyInfo(key=i, type=Bytes) for i in range(MAX_VOUCHERS)]
)
```

### Logic branches

When using the `AppBuilder` class,
the resulting approval program will feature the following branches:

| Condition | Result |
| - |
| `Txn.application_id() == Int(0)` | Initialize the state |
| `OnComplete == DeleteApplication` | Delete the state and programs |
| `OnComplete == UpdateApplication` | Update the programs |
| `OnComplete == OptIn` | Initialize the local state |
| `OnComplete == CloseOut` | Delete the local state |
| `OnComplete == NoOp` <br/> `Txn.application_args[0] == Bytes(name)` | Call the invocation with `name` |
| `OnComplete == NoOp` | Call the default invocation |

Exactly one branch will execute,
or the program will return an error (which rejects the transaction).

The creation branch triggers when the app ID is zero,
which happens only when a call is made to an app not yet on the chain.

The `NoOp` code signals the intent for a generic application call,
and if it is supplied with an argument at index 0 which matches an invocation name,
that invocation's logic is run.
If the `NoOp` code is used with no argument at index 0,
or this argument does not match an invocation name,
a default invocation is run.

In this demo application,
there are two invocations:
vouching for an account (`vouch_for`),
and receiving a vouch (`vouch_from`).

```python
# the previous txn in the group is that sent by the voucher
voucher_txn = Gtxn[Txn.group_index() - Int(1)]
# the 3rd argument of the vouchee txn is the index to write to
vouch_key = Txn.application_args[2]
vouch_idx = Btoi(vouch_key)

builder = apps.AppBuilder(
    invocations={
        # always allow the voucher to send this invocation along with the
        # vouchee address
        "vouch_for": Return(apps.ONE),
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
            # ensure vouch is being stored in an allowed index
            Assert(vouch_idx < Int(MAX_VOUCHERS)),
            # store the voucher's address in the given vouch index
            App.localPut(Txn.sender(), vouch_key, voucher_txn.sender()),
            Return(apps.ONE),
        ),
    },
    local_state=state,
)
```

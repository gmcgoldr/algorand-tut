---
layout: page
title: Testing
---

The following explains how to test an application.
The associated code can be found in `test_app_vouch.py`.
Note that in the following code snippets,
algo-app-dev and its testing module are imported into the namespace
(i.e. `from algoappdev import *` and `from algoappdev.testing import *` are assumed).

## Testing module

The `algoappdev.testing` module includes some useful fixtures for testing apps with `pytest`.

Set the environment variable `AAD_NODE_DIR` to the node's data directory
(e.g. `nets/private_dev/Primary`).
Then, the fixtures can be used to quickly access get the
`algod_client`, `kmd_client`, and a `funded_account`.

```python
from algoappdev.testing import *
```

The value of `testing.WAIT_ROUNDS` is loaded from the environment variable `AAD_WAIT_ROUNDS`.
When testing with a non-dev node,
then this should be set to a value of 5 or greater,
to give the network time to confirm transactions.

## Dry runs

The `algoappdev.dryruns` module helps setup dry runs for app calls.
These should be the first tool used when testing an app,
as they execute very quickly and return useful debugging information.

Here is a simple example of how to use the `dryruns` module to test the `set_name` branch:

```python
def test_can_set_name(algod_client: AlgodClient):
    # The `AlgodClient` connected to the node with data in `NODE_DIR` will be
    # constructed and passed along by `pytest`. It is needed to compile the
    # TEAL source into program bytes, and to execute the dry run.

    app_builder = app_vouch.build_app()

    # build a dummy address (will not need to sign anything with it)
    address_1 = dryruns.idx_to_address(1)

    result = algod_client.dryrun(
        # construct an object which will fully specify the context in which the
        # app call is run (i.e. set all arguments)
        dryruns.AppCallCtx()
        # add an app to the context, use the programs from the `app_builder`,
        # and set the app id to 1
        .with_app(app_builder.build_application(algod_client, 1))
        # add an account opted into the last app
        .with_account_opted_in(address=address_1)
        # create a no-op call with the last account
        .with_txn_call(args=["set_name", "abc"])
        # build the dryrun request
        .build_request()
    )

    # raise any errors in the dryrun result
    dryruns.check_err(result)
    # ensure the program returned non-zero
    assert dryruns.get_messages(result) == ["ApprovalProgram", "PASS"]
    # ensure the program changed the account's local state
    assert dryruns.get_local_deltas(result) == {
        address_1: [dryruns.KeyDelta(b"name", b"abc")]
    }
```

The `dryruns.get_trace` function can be used to iterate over stack trace lines,
for when things do go wrong.

Integration tests should still involve sending proper transactions,
though doing so with a node in dev mode can help speed things up significantly.
Ultimately, some tests should be run in the actual test net.

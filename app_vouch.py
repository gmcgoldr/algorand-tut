from algoappdev import *
from pyteal import *

MAX_VOUCHERS = 8


def build_app() -> apps.AppBuilder:
    # the state consists of 8 indices each for a voucher address
    state = apps.StateLocal(
        [apps.State.KeyInfo(key="name", type=Bytes)]
        + [
            apps.State.KeyInfo(key=f"voucher_{i}", type=Bytes)
            for i in range(MAX_VOUCHERS)
        ]
    )

    # the previous txn in the group is that sent by the voucher
    voucher_txn = Gtxn[Txn.group_index() - Int(1)]
    # the 3rd argument of the vouchee txn is the index to write to
    vouch_key = Txn.application_args[2]
    # valid vouch keys
    vouch_keys = [
        Bytes(state.key_info(f"voucher_{i}").key) for i in range(MAX_VOUCHERS)
    ]

    return apps.AppBuilder(
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

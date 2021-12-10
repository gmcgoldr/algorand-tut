from algoappdev import *
from pyteal import *

MAX_VOUCHERS = 8


def build_app() -> apps.AppBuilder:
    # the state consists of 8 indices each for a voucher address
    state = apps.StateLocal(
        [apps.State.KeyInfo(key=i, type=Bytes) for i in range(MAX_VOUCHERS)]
    )

    # the previous txn in the group is that sent by the voucher
    voucher_txn = Gtxn[Txn.group_index() - Int(1)]
    # the 3rd argument of the vouchee txn is the index to write to
    vouch_key = Txn.application_args[2]
    vouch_idx = Btoi(vouch_key)

    return apps.AppBuilder(
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

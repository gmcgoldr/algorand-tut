import algoappdev as aad
import pyteal as tl

MAX_VOUCHERS = 8


def build_app() -> aad.apps.AppBuilder:
    state = aad.apps.StateLocal(
        [aad.apps.State.KeyInfo(key=i, type=tl.Bytes) for i in range(8)]
    )

    voucher_txn = tl.Gtxn[tl.Txn.group_index() - tl.Int(1)]

    vouch_key = tl.Txn.application_args[2]
    vouch_idx = tl.Btoi(vouch_key)

    return aad.apps.AppBuilder(
        invocations={
            # voucher sends this app call with the vouchee address
            "vouch_for": tl.Return(aad.apps.ONE),
            # vouchee sends this app call
            "vouch_from": tl.Seq(
                # ensure voucher is using this contract
                tl.Assert(
                    voucher_txn.application_id() == tl.Global.current_application_id()
                ),
                # ensure voucher is vouching
                tl.Assert(voucher_txn.application_args[0] == tl.Bytes("vouch_for")),
                # ensure voucher is vouching for vouchee
                tl.Assert(voucher_txn.application_args[1] == tl.Txn.sender()),
                # ensure vouchee is getting vouch from voucher
                tl.Assert(tl.Txn.application_args[1] == voucher_txn.sender()),
                # ensure vouchee has no more than 8 vouches
                tl.Assert(vouch_idx < tl.Int(MAX_VOUCHERS)),
                # store the voucher's address in the given vouch index
                tl.App.localPut(tl.Txn.sender(), vouch_key, voucher_txn.sender()),
                tl.Return(aad.apps.ONE),
            ),
        },
        local_state=state,
    )

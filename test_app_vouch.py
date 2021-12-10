from algoappdev import dryruns
from algoappdev.testing import *
from algosdk.encoding import decode_address

import app_vouch


def test_approves_vouch(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_account_opted_in(address=address_2)
        .with_txn_call(sender=address_1, args=[b"vouch_for", decode_address(address_2)])
        .with_txn_call(
            sender=address_2,
            args=[
                b"vouch_from",
                decode_address(address_1),
                app_builder.local_state.key_info(0).key,
            ],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1) == ["ApprovalProgram", "PASS"]
    assert dryruns.get_local_deltas(result, 1) == {
        address_2: [
            dryruns.KeyDelta(
                app_builder.local_state.key_info(0).key, decode_address(address_1)
            )
        ]
    }

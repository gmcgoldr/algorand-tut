from algoappdev import *
from algoappdev.testing import *
from algosdk.encoding import decode_address
from algosdk.future.transaction import ApplicationNoOpTxn, ApplicationOptInTxn

import app_vouch


def test_can_set_name(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["set_name", "abc"])
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result) == ["ApprovalProgram", "PASS"]
    assert dryruns.get_local_deltas(result) == {
        address_1: [dryruns.KeyDelta(b"name", b"abc")]
    }


def test_can_vouch(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_2)])
        .with_account_opted_in(address=address_2)
        .with_txn_call(
            args=["vouch_from", decode_address(address_1), "voucher_0"],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1) == ["ApprovalProgram", "PASS"]
    assert dryruns.get_local_deltas(result, 1) == {
        address_2: [dryruns.KeyDelta(b"voucher_0", decode_address(address_1))]
    }


def test_set_name_removes_vouches(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(
            address=address_1,
            local_state=[
                utils.to_key_value(
                    f"voucher_{i}".encode("utf8"), decode_address(address_2)
                )
                for i in range(app_vouch.MAX_VOUCHERS)
            ],
        )
        .with_txn_call(args=["set_name", "abc"])
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result) == ["ApprovalProgram", "PASS"]

    deltas = dryruns.get_local_deltas(result)[address_1]
    assert set(deltas) == set(
        # set the name
        [dryruns.KeyDelta(b"name", b"abc")]
        # cleared all previous vouches
        + [
            dryruns.KeyDelta(f"voucher_{i}".encode("utf8"), None)
            for i in range(app_vouch.MAX_VOUCHERS)
        ]
    )


def test_cannot_vouch_past_max(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_2)])
        .with_account_opted_in(address=address_2)
        .with_txn_call(
            args=[
                "vouch_from",
                decode_address(address_1),
                f"voucher_{app_vouch.MAX_VOUCHERS}",
            ],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1)[:2] == ["ApprovalProgram", "REJECT"]


def test_cannot_vouch_without_voucher(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_2)])
        .with_account_opted_in(address=address_2)
        .with_txn_call(
            args=[
                "vouch_from",
                decode_address(address_1),
                f"voucher_{app_vouch.MAX_VOUCHERS}",
            ],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1)[:2] == ["ApprovalProgram", "REJECT"]


def test_cannot_vouch_without_vouchee(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_2)])
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 0) == ["ApprovalProgram", "PASS"]
    # vouch for is allowed, but changes nothing
    assert not dryruns.get_local_deltas(result, 0)


def test_cannot_vouch_with_wrong_voucher(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)
    address_3 = dryruns.idx_to_address(3)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_2)])
        .with_account_opted_in(address=address_2)
        .with_txn_call(
            args=["vouch_from", decode_address(address_3), "voucher_0"],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1)[:2] == ["ApprovalProgram", "REJECT"]


def test_cannot_vouch_with_wrong_vouchee(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)
    address_3 = dryruns.idx_to_address(3)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_3)])
        .with_account_opted_in(address=address_2)
        .with_txn_call(
            args=["vouch_from", decode_address(address_1), "voucher_0"],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1)[:2] == ["ApprovalProgram", "REJECT"]


def test_cannot_vouch_with_other_app_voucher(algod_client: AlgodClient):
    app_builder = app_vouch.build_app()

    address_1 = dryruns.idx_to_address(1)
    address_2 = dryruns.idx_to_address(2)

    result = algod_client.dryrun(
        dryruns.AppCallCtx()
        .with_app(app_builder.build_application(algod_client, 1))
        .with_account_opted_in(address=address_1)
        .with_txn_call(args=["vouch_for", decode_address(address_2)])
        # NOTE: different app id
        .with_app(app_builder.build_application(algod_client, 2))
        .with_account_opted_in(address=address_2)
        .with_txn_call(
            args=["vouch_from", decode_address(address_1), "voucher_0"],
        )
        .build_request()
    )

    dryruns.check_err(result)
    assert dryruns.get_messages(result, 1)[:2] == ["ApprovalProgram", "REJECT"]


def test_integration(algod_client: AlgodClient, funded_account: AccountMeta):
    app_builder = app_vouch.build_app()

    txn = app_builder.create_txn(
        algod_client, funded_account.address, algod_client.suggested_params()
    )
    txid = algod_client.send_transaction(txn.sign(funded_account.key))
    app_meta = utils.AppMeta.from_result(
        transactions.get_confirmed_transaction(algod_client, txid, WAIT_ROUNDS)
    )

    txn = ApplicationOptInTxn(
        funded_account.address, algod_client.suggested_params(), app_meta.app_id
    )
    txid = algod_client.send_transaction(txn.sign(funded_account.key))
    transactions.get_confirmed_transaction(algod_client, txid, testing.WAIT_ROUNDS)

    txn = ApplicationNoOpTxn(
        funded_account.address,
        algod_client.suggested_params(),
        app_meta.app_id,
        ["set_name", "Name"],
    )
    txid = algod_client.send_transaction(txn.sign(funded_account.key))
    transactions.get_confirmed_transaction(algod_client, txid, testing.WAIT_ROUNDS)

    txns = transactions.group_txns(
        ApplicationNoOpTxn(
            funded_account.address,
            algod_client.suggested_params(),
            app_meta.app_id,
            ["vouch_for", decode_address(funded_account.address)],
        ),
        ApplicationNoOpTxn(
            funded_account.address,
            algod_client.suggested_params(),
            app_meta.app_id,
            [
                "vouch_from",
                decode_address(funded_account.address),
                app_builder.local_state.key_info("voucher_0").key,
            ],
        ),
    )
    txns = [txns[0].sign(funded_account.key), txns[1].sign(funded_account.key)]
    txids = algod_client.send_transactions(txns)
    transactions.get_confirmed_transaction(algod_client, txid, testing.WAIT_ROUNDS)

    assert (
        clients.get_app_local_key(
            algod_client.account_info(funded_account.address),
            app_meta.app_id,
            b"name",
        )
        == b"Name"
    )

    assert (
        clients.get_app_local_key(
            algod_client.account_info(funded_account.address),
            app_meta.app_id,
            b"voucher_0",
        )
        == decode_address(funded_account.address)
    )

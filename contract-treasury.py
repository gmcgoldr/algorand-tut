"""
Build a periodic payment contract, deploy on a network, and execute the
payments.
"""

import base64
from pathlib import Path
from typing import List

import algosdk as ag
import pyteal as tl
from algosdk.future import transaction
from algosdk.v2client.algod import AlgodClient

from algorand_tut import contracts, utils


def get_app_global_key(algod_client: AlgodClient, app_id: int, key: str):
    key = base64.b64encode(key.encode("utf8")).decode("ascii")
    app_info = algod_client.application_info(app_id)
    for key_state in app_info["params"]["global-state"]:
        if key_state["key"] != key:
            continue
        return key_state["value"]
    raise KeyError(f"key {key} not found for app {app_id}")


def get_app_local_key(algod_client: AlgodClient, app_id: int, address: str, key: str):
    key = base64.b64encode(key.encode("utf8")).decode("ascii")
    account_info = algod_client.account_info(address)
    for app_state in account_info["apps-local-state"]:
        if app_state["id"] != app_id:
            continue
        for key_state in app_state["key-value"]:
            if key_state["key"] != key:
                continue
            return key_state["value"]
    raise KeyError(f"key {key} not found for app {app_id} at {address}")


def print_state(algod_client: AlgodClient, app_id: int, addresses: List[str]):
    print("Global:")
    print(get_app_global_key(algod_client, app_id, "count"))
    for address in addresses:
        print(f"Account {address}:")
        try:
            print(get_app_local_key(algod_client, app_id, address, "count"))
        except KeyError:
            print("EMPTY")


def main(node_data_dir: Path):
    algod_client = utils.build_algod_client(node_data_dir)
    kmd_client = utils.build_kmd_client(node_data_dir)

    app = contracts.build_distributed_treasury_app()
    tl.compileTeal(app.approval, mode=tl.Mode.Application, version=tl.MAX_TEAL_VERSION)
    tl.compileTeal(app.clear, mode=tl.Mode.Application, version=tl.MAX_TEAL_VERSION)

    print("Funding accounts ...")
    account1_private_key, account1_address = utils.fund_from_genesis(
        algod_client, kmd_client, ag.util.algos_to_microalgos(10)
    )
    account2_private_key, account2_address = utils.fund_from_genesis(
        algod_client, kmd_client, ag.util.algos_to_microalgos(10)
    )

    print("Building contract ...")
    params = algod_client.suggested_params()
    params.fee = 0
    # Compile the langauge binding to a TEAL program.
    app = contracts.build_distributed_treasury_app()
    txn = transaction.ApplicationCreateTxn(
        sender=account1_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC.real,
        approval_program=utils.compile_teal_source(
            tl.compileTeal(
                app.approval, mode=tl.Mode.Application, version=tl.MAX_TEAL_VERSION
            )
        ),
        clear_program=utils.compile_teal_source(
            tl.compileTeal(
                app.clear, mode=tl.Mode.Application, version=tl.MAX_TEAL_VERSION
            )
        ),
        global_schema=app.global_schema,
        local_schema=app.local_schema,
    )

    txid = algod_client.send_transaction(txn.sign(account1_private_key))
    result = utils.get_confirmed_transaction(algod_client, txid, 5)
    app_id = result["application-index"]

    print_state(algod_client, app_id, [account1_address, account2_address])

    print("Opting into contract ...")
    params = algod_client.suggested_params()
    params.fee = 0

    txn = transaction.ApplicationOptInTxn(account1_address, params, app_id)
    txid = algod_client.send_transaction(txn.sign(account1_private_key))
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)

    txn = transaction.ApplicationOptInTxn(account2_address, params, app_id)
    txid = algod_client.send_transaction(txn.sign(account2_private_key))
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)

    print_state(algod_client, app_id, [account1_address, account2_address])

    print("Incrementing ...")
    params = algod_client.suggested_params()
    params.fee = 0

    txn = transaction.ApplicationNoOpTxn(
        account1_address, params, app_id, [b"increment"]
    )
    txid = algod_client.send_transaction(txn.sign(account1_private_key))
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)

    txn = transaction.ApplicationNoOpTxn(
        account2_address, params, app_id, [b"increment"]
    )
    txid = algod_client.send_transaction(txn.sign(account2_private_key))
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)

    print_state(algod_client, app_id, [account1_address, account2_address])

    params = algod_client.suggested_params()
    txn = transaction.ApplicationCloseOutTxn(account1_address, params, app_id)
    txid = algod_client.send_transaction(txn.sign(account1_private_key))
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)

    print_state(algod_client, app_id, [account1_address, account2_address])

    params = algod_client.suggested_params()
    txn = transaction.ApplicationClearStateTxn(account2_address, params, app_id)
    txid = algod_client.send_transaction(txn.sign(account2_private_key))
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)

    print_state(algod_client, app_id, [account1_address, account2_address])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("node_data_dir", type=Path)
    main(**vars(parser.parse_args()))

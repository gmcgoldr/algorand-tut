"""
Build a periodic payment contract, deploy on a network, and execute the
payments.
"""

import base64
import time
from pathlib import Path
from typing import Dict, List

import algosdk as ag
from algosdk.future import transaction
from algosdk.future.transaction import PaymentTxn
from algosdk.v2client.algod import AlgodClient

from algorand_tut import contracts, utils


def get_app_global_key(algod_client: AlgodClient, app_id: int, key: str):
    """
    Return the value for the given `key` in `app_id`'s global data.
    """
    key = base64.b64encode(key.encode("utf8")).decode("ascii")
    app_info = algod_client.application_info(app_id)
    for key_state in app_info.get("params", {}).get("global-state", []):
        if key_state.get("key", None) != key:
            continue
        return key_state.get("value", None)
    return None


def get_app_local_key(algod_client: AlgodClient, app_id: int, address: str, key: str):
    """
    Return the value for the given `key` in `app_id`'s local data for account
    `address`.
    """
    key = base64.b64encode(key.encode("utf8")).decode("ascii")
    account_info = algod_client.account_info(address)
    for app_state in account_info.get("apps-local-state", []):
        if app_state.get("id", None) != app_id:
            continue
        for key_state in app_state.get("key-value", []):
            if key_state.get("key", None) != key:
                continue
            return key_state.get("value", None)
    return None


def extract_state_value(value: Dict):
    if value is None:
        return None
    if value.get("type", None) == 1:
        return value.get("bytes", None)
    if value.get("type", None) == 2:
        return value.get("uint", None)


def print_state(
    algod_client: AlgodClient, app_id: int, app_address: str, addresses: List[str]
):
    """
    Print the app's global data, and local data for `addressses`.
    """
    global_keys = [
        "funds_current",
        "funds_future",
        "votes_for",
        "votes_against",
        "term_used",
        "term_budget",
        "nominee",
        "last_nomination",
    ]

    local_keys = [
        "funds_current",
        "funds_future",
        "votes_for",
        "votes_against",
        "last_nomination",
        "last_vote",
    ]

    print(f"\nGlobal:")
    for key in global_keys:
        value = get_app_global_key(algod_client, app_id, key)
        value = extract_state_value(value)
        print(f"{key}: {value}")
    info = algod_client.account_info(app_address)
    print(
        "balance: {:.6f} Algos".format(
            ag.util.microalgos_to_algos(info.get("amount", 0))
        )
    )

    for address in addresses:
        print(f"\nAccount {address[:8]}:")
        for key in local_keys:
            value = get_app_local_key(algod_client, app_id, address, key)
            value = extract_state_value(value)
            print(f"{key}: {value}")
        info = algod_client.account_info(address)
        print(
            "balance: {:.6f} Algos".format(
                ag.util.microalgos_to_algos(info.get("amount", 0))
            )
        )

    print()


def main(node_data_dir: Path):
    algod_client = utils.build_algod_client(node_data_dir)
    kmd_client = utils.build_kmd_client(node_data_dir)
    wait_blocks = 5

    voting_duration = 30
    term_duration = 30
    cooldown = 10

    app = contracts.build_distributed_treasury_app(
        voting_duration=voting_duration, term_duration=term_duration, cooldown=cooldown
    )

    print("Funding accounts ...")
    account1, txid1 = utils.fund_from_genesis(
        algod_client,
        kmd_client,
        ag.util.algos_to_microalgos(100),
    )
    account2, txid2 = utils.fund_from_genesis(
        algod_client,
        kmd_client,
        ag.util.algos_to_microalgos(100),
    )
    assert (
        len(utils.get_confirmed_transactions(algod_client, [txid1, txid2], wait_blocks))
        == 2
    )

    print("Building app ...")
    params = algod_client.suggested_params()
    params.fee = 0  # use the minimum network fee
    # compile the programs and package into app creation txn
    txn = utils.build_app_from_build_info(app, account1.address, params)
    txid = algod_client.send_transaction(txn.sign(account1.key))
    result = utils.get_confirmed_transaction(algod_client, txid, wait_blocks)
    # thet the id of the created app, this is effectively the app's address,
    # as this is where app state change transactions are sent
    app_id = result["application-index"]
    # TODO: move to utils
    app_address = ag.encoding.encode_address(
        ag.encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
    )
    print(f"App: {app_id}, {app_address}")
    # the app's id can also be found in the creating account's info
    account_info = algod_client.account_info(account1.address)
    created_app_ids = [a["id"] for a in account_info["created-apps"]]
    assert app_id in created_app_ids
    print_state(algod_client, app_id, app_address, [account1.address, account2.address])

    print("Opting into contract ...")
    params = algod_client.suggested_params()
    params.fee = 0
    txn = transaction.ApplicationOptInTxn(account1.address, params, app_id)
    txid1 = algod_client.send_transaction(txn.sign(account1.key))
    txn = transaction.ApplicationOptInTxn(account2.address, params, app_id)
    txid2 = algod_client.send_transaction(txn.sign(account2.key))
    assert (
        len(utils.get_confirmed_transactions(algod_client, [txid1, txid2], wait_blocks))
        == 2
    )
    print_state(algod_client, app_id, app_address, [account1.address, account2.address])

    print("Adding funds ...")
    params = algod_client.suggested_params()
    params.fee = 0
    txns = utils.group_txns(
        PaymentTxn(
            account1.address, params, app_address, ag.util.algos_to_microalgos(10)
        ),
        transaction.ApplicationNoOpTxn(
            account1.address, params, app_id, ["add_funds".encode("utf8")]
        ),
    )
    txns = [t.sign(account1.key) for t in txns]
    txid1 = algod_client.send_transactions(txns)
    txns = utils.group_txns(
        PaymentTxn(
            account2.address, params, app_address, ag.util.algos_to_microalgos(5)
        ),
        transaction.ApplicationNoOpTxn(
            account2.address, params, app_id, ["add_funds".encode("utf8")]
        ),
    )
    txns = [t.sign(account2.key) for t in txns]
    txid2 = algod_client.send_transactions(txns)
    assert (
        len(utils.get_confirmed_transactions(algod_client, [txid1, txid2], wait_blocks))
        == 2
    )
    print_state(algod_client, app_id, app_address, [account1.address, account2.address])

    print("Nominating ...")
    params = algod_client.suggested_params()
    params.fee = 0
    txn = transaction.ApplicationNoOpTxn(
        account1.address,
        params,
        app_id,
        ["nominate".encode("utf8"), ag.util.algos_to_microalgos(15)],
    )
    txid = algod_client.send_transaction(txn.sign(account1.key))
    assert utils.get_confirmed_transaction(algod_client, txid, wait_blocks)
    voting_end = time.time() + voting_duration
    print_state(algod_client, app_id, app_address, [account1.address, account2.address])

    print("Voting ...")
    params = algod_client.suggested_params()
    params.fee = 0
    txn = transaction.ApplicationNoOpTxn(
        account1.address, params, app_id, ["vote_for".encode("utf8")]
    )
    txid1 = algod_client.send_transaction(txn.sign(account1.key))
    txn = transaction.ApplicationNoOpTxn(
        account2.address, params, app_id, ["vote_against".encode("utf8")]
    )
    txid2 = algod_client.send_transaction(txn.sign(account2.key))
    assert (
        len(utils.get_confirmed_transactions(algod_client, [txid1, txid2], wait_blocks))
        == 2
    )
    print_state(algod_client, app_id, app_address, [account1.address, account2.address])

    print("Waiting for voting to end ...")
    time.sleep(max(0, voting_end - time.time()))

    print("Windrawing ...")
    params = algod_client.suggested_params()
    params.fee = 0
    txn = transaction.ApplicationNoOpTxn(
        account1.address,
        params,
        app_id,
        ["withdraw_funds".encode("utf8"), ag.util.algos_to_microalgos(10)],
    )
    txid = algod_client.send_transaction(txn.sign(account1.key))
    assert utils.get_confirmed_transaction(algod_client, txid, wait_blocks)
    print_state(algod_client, app_id, app_address, [account1.address, account2.address])

    # TODO: is it possible to make multiple transactions with the same app
    # in the same block? Hopefully not ...


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("node_data_dir", type=Path)
    main(**vars(parser.parse_args()))

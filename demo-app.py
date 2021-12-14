#!/usr/bin/env python3

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from algoappdev import *
from algosdk.encoding import decode_address, encode_address
from algosdk.future.transaction import ApplicationNoOpTxn, ApplicationOptInTxn
from algosdk.util import algos_to_microalgos

from app_vouch import MAX_VOUCHERS, build_app


def main(node_data_dir: Path):
    app_builder = build_app()

    algod_client = clients.build_algod_local_client(node_data_dir)
    kmd_client = clients.build_kmd_local_client(node_data_dir)

    names = ["alice", "bob", "charlie", "dave", "erin", "frank", "grace"]

    # fund the accounts
    txn_ids: List[str] = []
    accounts: Dict[str, utils.AccountMeta] = {}
    for name in names:
        print(f"funding {name}")
        account, txid = transactions.fund_from_genesis(
            algod_client, kmd_client, algos_to_microalgos(1)
        )
        accounts[name] = account
        txn_ids.append(txid)
    # wait until funding has been confrimed
    transactions.get_confirmed_transactions(algod_client, txn_ids, testing.WAIT_ROUNDS)

    # build the app
    print("building app")
    txn = app_builder.create_txn(
        algod_client, accounts["alice"].address, algod_client.suggested_params()
    )
    txid = algod_client.send_transaction(txn.sign(accounts["alice"].key))
    # get its id and address (needed to make calls to it)
    app = utils.AppMeta.from_result(
        transactions.get_confirmed_transaction(algod_client, txid, testing.WAIT_ROUNDS)
    )

    # opt-in the accounts to the app
    txn_ids: List[str] = []
    for name in names:
        print(f"opting in {name}")
        txn = ApplicationOptInTxn(
            accounts[name].address, algod_client.suggested_params(), app.app_id
        )
        txn_ids.append(algod_client.send_transaction(txn.sign(accounts[name].key)))
    # wait until the transactions have been confirmed
    transactions.get_confirmed_transactions(algod_client, txn_ids, testing.WAIT_ROUNDS)

    # adding credentials: setting the name
    txn_ids: List[str] = []
    for name in names:
        print(f"adding credentials for {name}")
        txn = ApplicationNoOpTxn(
            accounts[name].address,
            algod_client.suggested_params(),
            app.app_id,
            ["set_name", name.encode("utf8")],
        )
        txn_ids.append(algod_client.send_transaction(txn.sign(accounts[name].key)))
    # wait until the transactions have been confirmed
    transactions.get_confirmed_transactions(algod_client, txn_ids, testing.WAIT_ROUNDS)

    # create a graph of vouches
    vouches = [
        ("alice", "bob"),
        ("alice", "charlie"),
        ("bob", "dave"),
        ("charlie", "dave"),
        ("erin", "grace"),
        ("frank", "grace"),
        ("charlie", "grace"),
    ]
    # keep track of how many vouches each name received
    num_vouches = defaultdict(int)

    txn_ids: List[str] = []
    for name_1, name_2 in vouches:
        print(f"{name_1} vouching for {name_2}")
        # use the next available vouch in the vouchee account
        vouch_idx = num_vouches[name_2]
        num_vouches[name_2] += 1
        # the app logic requires that both parties agree to the vouch
        txns = transactions.group_txns(
            ApplicationNoOpTxn(
                accounts[name_1].address,
                algod_client.suggested_params(),
                app.app_id,
                ["vouch_for", decode_address(accounts[name_2].address)],
            ),
            ApplicationNoOpTxn(
                accounts[name_2].address,
                algod_client.suggested_params(),
                app.app_id,
                [
                    "vouch_from",
                    decode_address(accounts[name_1].address),
                    app_builder.local_state.key_info(f"voucher_{vouch_idx}").key,
                ],
            ),
        )
        # submit the transactions in a group
        txns = [txns[0].sign(accounts[name_1].key), txns[1].sign(accounts[name_2].key)]
        txn_ids.append(algod_client.send_transactions(txns))
    # wait until the transactions have been confirmed
    transactions.get_confirmed_transactions(algod_client, txn_ids, testing.WAIT_ROUNDS)

    # get the names as stored in the app credentials
    address_to_name = {
        a.address: clients.get_app_local_key(
            algod_client.account_info(a.address),
            app.app_id,
            app_builder.local_state.key_info("name").key,
        )
        for a in accounts.values()
    }

    # extract vouch information from the accounts
    print("\nParticipants:")
    address_to_name = {a.address: n for n, a in accounts.items()}
    for name in names:
        account = accounts[name]
        vouchers = []
        for vouch_idx in range(MAX_VOUCHERS):
            voucher_address = clients.get_app_local_key(
                algod_client.account_info(account.address),
                app.app_id,
                app_builder.local_state.key_info(f"voucher_{vouch_idx}").key,
            )
            if not voucher_address:
                continue
            voucher_address = encode_address(voucher_address)
            vouchers.append(address_to_name[voucher_address])
        print("{:8s}: {}".format(name, ", ".join(vouchers)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("node_data_dir", type=Path)
    main(**vars(parser.parse_args()))

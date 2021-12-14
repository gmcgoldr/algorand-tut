#!/usr/bin/env python3

from pathlib import Path

from algoappdev import *
from algosdk.account import generate_account
from algosdk.future.transaction import PaymentTxn
from algosdk.mnemonic import from_private_key
from algosdk.util import algos_to_microalgos, microalgos_to_algos
from algosdk.wallet import Wallet


def main(node_data_dir: Path):
    algod_client = clients.build_algod_local_client(node_data_dir)
    kmd_client = clients.build_kmd_local_client(node_data_dir)

    # get the address of the first account in the wallet
    wallet = Wallet("unencrypted-default-wallet", "", kmd_client)
    sender = wallet.list_keys()[0]

    print("Account details:")

    print(f"  genesis address: {sender}")

    # Create a new standalone account. It is also be possible to create an
    # account managed by a wallet with `kmd`.
    # See: https://developer.algorand.org/docs/features/accounts/create/
    receiver_key, receiver = generate_account()
    print(f"  new address: {receiver}")
    print(f"  passphrase : {from_private_key(receiver_key)}")

    print("Balances:")
    to_account_info = algod_client.account_info(receiver)
    from_account_info = algod_client.account_info(sender)
    print(
        "  from: {:.6f} Algos".format(
            microalgos_to_algos(from_account_info.get("amount", 0))
        )
    )
    print(
        "  to  : {:.6f} Algos".format(
            microalgos_to_algos(to_account_info.get("amount", 0))
        )
    )

    print("Move Algos:")
    # Can add arbitrary binary data (up to 1000 bytes) to the transaction.
    note = "Hello World".encode()
    # Get defaults for the transaction parameters. In particular, there is a
    # network-wide minimum transaction fee and maximum transaction duration.
    # This will recommend the minimum fee and will set the first valid block
    # to the current block, and the last valid block to the max duration from
    # the current block.
    # More: https://developer.algorand.org/docs/reference/transactions/
    params = algod_client.suggested_params()
    # The fee is calculated as:
    # `max(min_fee, fee if not flat_fee else (fee * num_bytes))`
    # where `min_fee` is the minimum fee enforced by the network, and
    # `num_bytes` is the size of the transaction. Setting the `fee` to zero
    # means the minimum is used.
    params.fee = 0
    txn = PaymentTxn(
        sender=sender,
        sp=params,
        receiver=receiver,
        amt=algos_to_microalgos(1),
        note=note,
    )
    # looksup the sender address in the wallet and uses its key to sign
    signed_txn = wallet.sign_transaction(txn)

    # Send the transaction and wait for it to be confirmed.
    txid = algod_client.send_transaction(signed_txn)
    print(f"  transaction ID: {txid}")
    print("  waiting for confirmation...")
    transactions.get_confirmed_transaction(algod_client, txid, 5)

    # Verify the account balances have changed.
    print("Balances:")
    to_account_info = algod_client.account_info(receiver)
    from_account_info = algod_client.account_info(sender)
    print(
        "  from: {:.6f} Algos".format(
            microalgos_to_algos(from_account_info.get("amount", 0))
        )
    )
    print(
        "  to  : {:.6f} Algos".format(
            microalgos_to_algos(to_account_info.get("amount", 0))
        )
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("node_data_dir", type=Path)
    main(**vars(parser.parse_args()))

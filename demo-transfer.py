#!/usr/bin/env python3

from pathlib import Path

import algosdk as ag
import pyteal_utils as ptu
from algosdk.future.transaction import PaymentTxn


def main(node_data_dir: Path):
    algod_client = ptu.clients.build_algod_local_client(node_data_dir)
    kmd_client = ptu.clients.build_kmd_local_client(node_data_dir)

    # Following the configuration in this repository, there should be an
    # account in the default wallet with funds. Get it's wallet such that it
    # can be used to send a payment.
    wallet_id = ptu.clients.get_wallet_id(
        kmd_client=kmd_client, name="unencrypted-default-wallet"
    )

    print("Account details:")

    # NOTE: the default wallet is unecrypted so no password is required
    with ptu.clients.get_wallet_handle(kmd_client, wallet_id, "") as handle:
        keys = kmd_client.list_keys(handle)
        if not keys:
            raise RuntimeError("funded account not found in wallet")
        from_address = keys[0]
    print(f"  genesis address: {from_address}")

    # Create a new standalone account. It is also be possible to create an
    # account managed by a wallet with `kmd`.
    # See: https://developer.algorand.org/docs/features/accounts/create/
    to_private_key, to_address = ag.account.generate_account()
    print(f"  new address: {to_address}")
    print(f"  passphrase : {ag.mnemonic.from_private_key(to_private_key)}")

    print("Balances:")
    to_account_info = algod_client.account_info(to_address)
    from_account_info = algod_client.account_info(from_address)
    print(
        "  from: {:.6f} Algos".format(
            ag.util.microalgos_to_algos(from_account_info.get("amount", 0))
        )
    )
    print(
        "  to  : {:.6f} Algos".format(
            ag.util.microalgos_to_algos(to_account_info.get("amount", 0))
        )
    )

    print("Move Algos:")
    # Can add aribtrary binary data (up to 1000 bytes) to the transaction.
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
    # where `min_fee` is the minimum fee enfoced by the netwrok, and
    # `num_bytes` is the size of the transaction. Setting the `fee` to zero
    # means the minimum is used.
    params.fee = 0
    txn = PaymentTxn(
        sender=from_address,
        sp=params,
        receiver=to_address,
        amt=ag.util.algos_to_microalgos(1),
        note=note,
    )

    # Sign the transaction, letting `kmd` manage the private key.
    with ptu.clients.get_wallet_handle(kmd_client, wallet_id, "") as handle:
        txn = kmd_client.sign_transaction(handle, "", txn)

    # Send the transaction and wait for it to be confirmed.
    txid = algod_client.send_transaction(txn)
    print(f"  transaction ID: {txid}")
    print("  waiting for confirmation...")
    txn = ptu.transactions.get_confirmed_transaction(algod_client, txid, 4)

    # Verify the account balances have changed.
    print("Balances:")
    to_account_info = algod_client.account_info(to_address)
    from_account_info = algod_client.account_info(from_address)
    print(
        "  from: {:.6f} Algos".format(
            ag.util.microalgos_to_algos(from_account_info.get("amount", 0))
        )
    )
    print(
        "  to  : {:.6f} Algos".format(
            ag.util.microalgos_to_algos(to_account_info.get("amount", 0))
        )
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("node_data_dir", type=Path)
    main(**vars(parser.parse_args()))

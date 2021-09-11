"""
Build a periodic payment contract, deploy on a network, and execute the
payments.
"""

import secrets
import sys
from pathlib import Path

import algosdk as ag
import pyteal as tl
from algosdk.future.transaction import LogicSigAccount, LogicSigTransaction, PaymentTxn
from algosdk.v2client.algod import AlgodClient

from algorand_tut import contracts, utils


def print_balances(
    algod_client: AlgodClient, sender_address: str, receiver_address: str
):
    sender_info = algod_client.account_info(sender_address)
    receiver_info = algod_client.account_info(receiver_address)
    print(
        "Sender balance: {:.6f} Algos".format(
            ag.util.microalgos_to_algos(sender_info.get("amount", 0))
        )
    )
    print(
        "Receiver balance: {:.6f} Algos".format(
            ag.util.microalgos_to_algos(receiver_info.get("amount", 0))
        )
    )


def main(node_data_dir: Path, use_delegate: bool):
    algod_client = utils.build_algod_client(node_data_dir)
    kmd_client = utils.build_kmd_client(node_data_dir)

    print("Funding source account ...")
    # Create a sender account with 10 algos to start
    sender_private_key, sender_address = utils.fund_from_genesis(
        algod_client, kmd_client, ag.util.algos_to_microalgos(10)
    )
    # Create an arbitrary receiver address where funds can be moved
    _, receiver_address = ag.account.generate_account()

    # Don't allow a contract to sign a transaction with any fee other than the
    # minimum network fee. This enforces that the maximum rate at which the
    # escrow account can drain is `amount + max_fee` per period.
    max_fee = ag.constants.MIN_TXN_FEE
    # Every 5 rounds, allow a payment.
    # NOTE: period must be long enough for a transaction to get confirmed.
    period = 5
    # Start at current period
    params = algod_client.suggested_params()
    start_round = params.first
    # Allow 3 payments (then the escrow acount can be closed out)
    num_periods = 3
    end_round = start_round + period * num_periods
    # Send 1 Algo at each period
    amount = ag.util.algos_to_microalgos(1)

    # The lease forms a key of the form `(sender, lease)` which acts as a lock.
    # The first transaction with this key to be confirmed acquires the lock. It
    # is released after the `last_valid` round. Other transactions with that
    # key (i.e. same sender and lease) are rejected until it is released. In
    # this case, the escrow account can pay out only once per period since the
    # `last_valid` marks the end of the period. This need not be random, but
    # if the escrow account were used in other contracts, and two leases used
    # the same value, there could be issues.
    lease = secrets.randbits(32 * 8).to_bytes(32, sys.byteorder)

    print("Building contract ...")
    # Compile the langauge binding to a TEAL program.
    contract = tl.compileTeal(
        contracts.build_periodic_payment(
            max_fee=max_fee,
            start_round=start_round,
            end_round=end_round,
            period=period,
            amount=amount,
            receiver=receiver_address,
            lease=lease,
        ),
        # This is a stateless contract
        mode=tl.Mode.Signature,
        # Use the latest features from the TEAL language
        version=tl.MAX_TEAL_VERSION,
    )
    # Compile the binary.
    contract = utils.compile_teal_source(contract)
    # Build the logical signature account.
    contract = LogicSigAccount(contract)

    if use_delegate:
        print("Delegating to the contract")
        # Make it so that the contract can sign transactions on the behalf of
        # the sender account when the transaction passes the contract logic
        contract.sign(sender_private_key)
    else:
        print("Funding the contract ...")
        # Move all funds from source into the contract, and wait for
        # confirmation
        params = algod_client.suggested_params()
        params.fee = 0  # use the minimum network fee
        txn = PaymentTxn(
            sender=sender_address,
            sp=params,
            receiver=utils.ZERO_ADDRESS,
            amt=0,
            close_remainder_to=contract.address(),
        )
        txid = algod_client.send_transaction(txn.sign(sender_private_key))
        _ = utils.get_confirmed_transaction(algod_client, txid, 5)
        # Use the contract as the sender now
        sender_address = contract.address()
        sender_private_key = None

    print_balances(algod_client, sender_address, receiver_address)

    # NOTE: the contract defines allowed transitions to the ledger, it is
    # still the job of the node to request the transitions to the network.

    print("Making periodic payments ...")
    for iperiod in range(num_periods):
        params = algod_client.suggested_params()
        params.fee = 0
        params.first = start_round + iperiod * period
        params.last = params.first + period - 1
        txn = PaymentTxn(
            sender=sender_address,
            sp=params,
            receiver=receiver_address,
            amt=amount,
            lease=lease,
        )
        txn = LogicSigTransaction(txn, contract)
        # wait until the first valid block for this transaction
        algod_client.status_after_block(params.first - 1)
        txid = algod_client.send_transaction(txn)
        # wait for the transaction to go through
        _ = utils.get_confirmed_transaction(algod_client, txid, 5)
        print_balances(algod_client, sender_address, receiver_address)

    print("Closing out the escrow account ...")
    params = algod_client.suggested_params()
    params.fee = 0
    params.first = end_round
    params.last = params.first + 1000
    txn = PaymentTxn(
        sender=sender_address,
        sp=params,
        receiver=utils.ZERO_ADDRESS,
        amt=0,
        close_remainder_to=receiver_address,
        lease=lease,
    )
    txn = LogicSigTransaction(txn, contract)
    # wait for the next payment window
    algod_client.status_after_block(params.first)
    txid = algod_client.send_transaction(txn)
    # wait for the transaction to go through
    _ = utils.get_confirmed_transaction(algod_client, txid, 5)
    print_balances(algod_client, sender_address, receiver_address)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("node_data_dir", type=Path)
    parser.add_argument("--use_delegate", action="store_true")
    main(**vars(parser.parse_args()))

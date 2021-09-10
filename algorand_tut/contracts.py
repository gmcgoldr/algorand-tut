"""
Construct TEAL contracts.

A TEAL program (a.k.a. contract) is evaluated with a transaction data structure
as its input (it can have more inputs), and outputs a single boolean which 
either approves or rejects the transactions.

In this module, python bindigs for TEAL are used to construct TEAL expressions.
These expressions can be compiled into TEAL programs.
"""

import pyteal as tl


def build_periodic_payment(
    max_fee: int,
    start_round: int,
    end_round: int,
    period: int,
    amount: int,
    receiver: str,
    lease: bytes,
) -> tl.Expr:
    """
    Builds a TEAL expression for recurring payments.

    Args:
        max_fee: don't allow transactions with fees above this
        start_round: start allowing payments at this round
        end_round: stop allowing payments at this round, and allow closing out
            the escrow account
        period: transaction can be repeated every `period` blocks
        lease: unique key identifies the period transaction
        amount: the quantity of Algos moved in the trasaction
        receiver: the receiver of the transaction
        lease: unique identifier for contracts which must be mutually exclusive
            in the same time period

    Returns:
        the TEAL expression
    """

    max_fee = tl.Int(max_fee)
    start_round = tl.Int(start_round)
    end_round = tl.Int(end_round)
    period = tl.Int(period)
    amount = tl.Int(amount)
    receiver = tl.Addr(receiver)
    lease = tl.Bytes("base16", lease.hex())

    # NOTE: the `Txn` object is used to access inputs to the program that come
    # from the transaction data structure.
    # See: https://developer.algorand.org/docs/reference/teal/specification/

    # Sign transactions with the following fields
    core = tl.And(
        # Must be a payment
        tl.Txn.type_enum() == tl.TxnType.Payment,
        # Cannot exceed the specified max fee, this keeps rate at which the
        # sending account drains bound to `amount + max_fee` per period
        tl.Txn.fee() <= max_fee,
        # Cannot preceed contract start (end handled in different cases)
        tl.Txn.first_valid() >= start_round,
        # Only allow transactions starting at rounds at the rate prescribed by
        # the given `period`
        (tl.Txn.first_valid() - start_round) % period == tl.Int(0),
        # This enforces the periodicity: only one transaction can be approved
        # by this contract
        tl.Txn.lease() == lease,
    )

    payment = tl.And(
        # Before end of periodic range
        tl.Txn.first_valid() < end_round,
        # Transaction is valid only until the next period, as the lase works
        # as a lock during the valdity window
        tl.Txn.last_valid() == tl.Txn.first_valid() + period - tl.Int(1),
        # Not close out the account
        tl.Txn.close_remainder_to() == tl.Global.zero_address(),
        # Not rekey
        tl.Txn.rekey_to() == tl.Global.zero_address(),
        # Be sent to the receiver of this contract
        tl.Txn.receiver() == receiver,
        # By sending the amount in the contract
        tl.Txn.amount() == amount,
    )

    # If this at the timeout, the transaction can close out the account
    close = tl.And(
        # at end of period range
        tl.Txn.first_valid() == end_round,
        # Close out the account
        tl.Txn.close_remainder_to() == receiver,
        # Not rekey
        tl.Txn.rekey_to() == tl.Global.zero_address(),
        # Not be sending an amount to a receipient (beyond the closing)
        tl.Txn.receiver() == tl.Global.zero_address(),
        tl.Txn.amount() == tl.Int(0),
    )

    # The overall contract allows transactions that are period payments, or
    # closing out the account
    return tl.And(core, tl.Or(payment, close))

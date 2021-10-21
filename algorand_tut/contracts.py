"""
Construct TEAL contracts.

A TEAL program (a.k.a. contract) is evaluated with a transaction data structure
as its input (it can have more inputs), and outputs a single boolean which 
either approves or rejects a transaction.

In this module, python bindigs for TEAL are used to construct TEAL expressions.
These expressions can be compiled into TEAL programs.
"""

from typing import List, NamedTuple, Tuple

import pyteal as tl
from algosdk.future import transaction
from pyteal.ast.app import OnComplete


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


class AppPrograms(NamedTuple):
    """Data required to build a stateful contract (app)."""

    approval: tl.Expr
    clear: tl.Expr
    global_schema: transaction.StateSchema
    local_schema: transaction.StateSchema


def new_app_program(
    on_create: tl.Expr = None,
    on_delete: tl.Expr = None,
    on_update: tl.Expr = None,
    on_opt_in: tl.Expr = None,
    on_close_out: tl.Expr = None,
    on_clear: tl.Expr = None,
    invokations: List[Tuple[tl.Bytes, tl.Expr]] = [],
    global_schema: transaction.StateSchema = transaction.StateSchema(),
    local_schema: transaction.StateSchema = transaction.StateSchema(),
) -> AppPrograms:
    """
    Build the program data required for an app to execute the provided
    expressions, with the provided storage schema.

    By default, this creates an app with no storage, and which only approves
    a cration transaction, and the delete transaction by its creator.

    Of the transaction-invoked state changes (e.g. opt-in, update etc.), only
    those with a provided expression are permitted, and only when that
    expression returns one.

    Additional state changes to the app's storage can be invoked by passing a
    string as the first argument. In that case, if there is a corresponding
    name in the `invokations` list, then it's expression will be evaluated, and
    if it returns one, then any state changes carried out will be committed.

    Invokations can be invoked only by accounts which have opted in.

    Args:
        on_create: expression to invoke if the application is not initialized
        on_delete: expression to invoke for deletion
        on_update: expression to invoke for update
        on_opt_in: expression to invoke for opt in
        on_close_out: expression to invoke for close out (opt out)
        on_clear: expression to invoke for clear (forced opt out)
        invokations: list of invokation names and corresponding expressions
        global_schema: global storage schema
        local_schema: local storage schema
    """
    zero = tl.Int(0)
    one = tl.Int(1)

    # by default, allow creation
    if on_create is None:
        on_create = tl.Return(one)
    # by default, allow the creator to delete the app
    if on_delete is None:
        on_delete = tl.Return(tl.Global.creator_address() == tl.Txn.sender())
    if on_clear is None:
        on_clear = tl.Return(one)

    # Each branch is a tuple of expressions: one which tests if the branch
    # should be executed, and another which is the branche's logic. If the
    # branch logic returns 0, then the app state is unchanged, no matter what
    # operations were performed during its exectuion (i.e. it rolls back). Only
    # the first matched branch is executed.
    branches = []

    if on_create:
        branches.append([tl.Txn.application_id() == zero, on_create])
    if on_delete:
        branches.append(
            [tl.Txn.on_completion() == tl.OnComplete.DeleteApplication, on_delete]
        )
    if on_update:
        branches.append(
            [tl.Txn.on_completion() == tl.OnComplete.UpdateApplication, on_update]
        )
    if on_close_out:
        branches.append(
            [tl.Txn.on_completion() == tl.OnComplete.CloseOut, on_close_out]
        )
    if on_opt_in:
        branches.append([tl.Txn.on_completion() == tl.OnComplete.OptIn, on_opt_in])
    for name, expr in invokations:
        branches.append(
            [
                tl.Txn.on_completion() == tl.OnComplete.NoOp
                and tl.Txn.application_args[0] == name,
                expr,
            ]
        )
    # this is a fall-through, if no branch matched, then no matter what is
    # requested by the transaction, deny it
    branches.append([one, tl.Return(zero)])

    return AppPrograms(
        approval=tl.Cond(*branches),
        clear=on_clear,
        global_schema=global_schema,
        local_schema=local_schema,
    )


def build_distributed_treasury_app() -> AppPrograms:
    key_count = tl.Bytes("count")

    zero = tl.Int(0)
    one = tl.Int(1)

    # fetch the global count
    global_count = tl.App.globalGet(key_count)
    # maybe fetch the sender count
    sender_count_ex = tl.App.localGetEx(tl.Txn.sender(), tl.App.id(), key_count)
    # execute the fetch, then return the feteched value or zero
    sender_count = tl.Seq([sender_count_ex, sender_count_ex.value()])

    on_create = tl.Seq(
        [
            tl.App.globalPut(key_count, zero),
            tl.Return(one),
        ]
    )

    on_opt_in = tl.Seq(
        [
            tl.App.localPut(tl.Txn.sender(), key_count, zero),
            tl.Return(one),
        ]
    )

    on_close_out = tl.Seq(
        [
            tl.App.globalPut(key_count, global_count - sender_count),
            tl.Return(one),
        ]
    )

    invokations = [
        (
            tl.Bytes("increment"),
            tl.Seq(
                [
                    tl.App.globalPut(key_count, global_count + one),
                    tl.App.localPut(tl.Txn.sender(), key_count, sender_count + one),
                    tl.Return(one),
                ]
            ),
        )
    ]

    global_schema = transaction.StateSchema(num_uints=1)
    local_schema = transaction.StateSchema(num_uints=1)

    return new_app_program(
        on_create=on_create,
        on_opt_in=on_opt_in,
        on_close_out=on_close_out,
        on_clear=on_close_out,
        invokations=invokations,
        global_schema=global_schema,
        local_schema=local_schema,
    )

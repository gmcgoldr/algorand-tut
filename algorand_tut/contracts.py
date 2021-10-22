"""
Construct TEAL contracts.

A TEAL program (a.k.a. contract) is evaluated with a transaction data structure
as its input (it can have more inputs), and outputs a single boolean which 
either approves or rejects a transaction.

In this module, python bindigs for TEAL are used to construct TEAL expressions.
These expressions can be compiled into TEAL programs.
"""

import pyteal as tl

from . import utils


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

    This is a smart signature, a statless contract. It can be thought of as a
    template where transactions matching the template are approved, and others
    are denied.

    In other words, the account which signed this contract effectively signed
    any transaction which matches this template.

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


def build_distributed_treasury_app() -> utils.AppBuildInfo:
    """
    Build the distributred treasury app build info.
    """

    zero = tl.Int(0)
    one = tl.Int(1)

    globals = utils.StateBuilder(
        utils.StateBuilder.Scope.GLOBAL,
        [
            # default keys
            utils.KeyInfo("funds_current", tl.Int, zero),
            utils.KeyInfo("funds_future", tl.Int, zero),
            utils.KeyInfo("votes_for", tl.Int, zero),
            utils.KeyInfo("votes_against", tl.Int, zero),
            utils.KeyInfo("term_used", tl.Int, zero),
            utils.KeyInfo("term_budget", tl.Int, zero),
            # optional keys
            utils.KeyInfo("nominee", tl.Bytes),
            utils.KeyInfo("last_nomination_ts", tl.Int),
        ],
    )

    locals = utils.StateBuilder(
        utils.StateBuilder.Scope.LOCAL,
        [
            # default keys
            utils.KeyInfo("funds_current", tl.Int, zero),
            utils.KeyInfo("funds_future", tl.Int, zero),
            utils.KeyInfo("votes_for", tl.Int, zero),
            utils.KeyInfo("votes_against", tl.Int, zero),
            # optional keys
            utils.KeyInfo("last_nomination_ts", tl.Int),
            utils.KeyInfo("last_vote_ts", tl.Int),
            utils.KeyInfo("last_funds_ts", tl.Int),
        ],
    )

    # according to docs, this is the exact method in which the application
    # address is calcualted: it is the SHA512 hash, with digest size 256, of
    # the bytes "appID" and the 8-byte big-endian encoding of the app id
    # TODO: hopefully this gets added to the globals eventually so it can be
    # looked up cheaply, because this is expensive
    app_address = tl.Sha512_256(tl.Concat(tl.Bytes("appID"), tl.Itob(tl.App.id())))

    cooldown = tl.Int(30)
    voting_duration = tl.Int(30)
    term_duration = tl.Int(60)

    timestamp = tl.Global.latest_timestamp()

    # the amount funded to the contract if it the app is the in a pair of
    # transactions, with the 1st paying the app
    fund_txn: tl.Txn = tl.Gtxn[0]
    amount_funded = tl.Seq(
        tl.If(
            tl.And(
                tl.Global.group_size() == tl.Int(2),
                tl.Txn.group_index() == tl.Int(1),
                fund_txn.type_enum() == tl.TxnType.Payment,
                fund_txn.receiver() == app_address,
            ),
            fund_txn.amount(),
            zero,
        )
    )

    is_state_voting = tl.And(
        # there is a nominee
        globals.maybe("nominee").hasValue(),
        # vote hasn't failed yet
        globals.get("votes_against") * tl.Int(2) < globals.get("funds_current"),
        # time since nomination is in voting window
        # NOTE: can use default value because nominee check ensures
        # `last_nomination_ts` is also set
        timestamp - globals.get("last_nomination_ts") <= voting_duration,
    )

    is_state_term = tl.And(
        tl.Not(is_state_voting),
        # there is a nominee
        globals.maybe("nominee").hasValue(),
        # vote passed
        globals.get("votes_for") * tl.Int(2) > globals.get("funds_current"),
        # term hasn't been fully utilized
        tl.And(
            globals.get("term_used") < globals.get("term_budget"),
            # further restrict term spend to votes for term, which never
            # exceeds current funds
            globals.get("term_used") < globals.get("votes_for"),
        ),
        # time since nomination is in term window
        voting_duration
        < timestamp - globals.get("last_nomination_ts")
        <= voting_duration + term_duration,
    )

    is_valid_nomination = tl.And(
        # only accept nominations outside voting and term
        tl.Not(is_state_voting),
        tl.Not(is_state_term),
        # ensure not during the account's cooldown
        tl.If(
            locals.maybe("last_nomination_ts").hasValue(),
            timestamp - locals.get("last_nomination_ts") > cooldown,
            one,  # hasn't yet nominated self, no cooldown
        ),
    )

    # remove an account's vote (to re-cast, or when closing out)
    remove_vote = tl.Seq(
        tl.If(
            # was last vote cast by this account in the current voting period
            tl.If(
                locals.maybe("last_vote_ts").hasValue(),
                timestamp - locals.get("last_vote_ts") <= voting_duration,
                zero,  # hasn't cast a vote
            ),
            # last cast is for current vote, so remove from global tally
            tl.Seq(
                globals.dec("votes_for", locals.get("votes_for")),
                globals.dec("votes_against", locals.get("votes_against")),
            ),
        ),
        # clear the local vote
        locals.set("votes_for", zero),
        locals.set("votes_against", zero),
    )

    # shift account funds from before last nomiation to current voting period
    update_funds = tl.Seq(
        tl.If(
            locals.get("last_funds_ts") < globals.get("last_nomination_ts"),
            tl.Seq(
                locals.inc("funds_current", locals.get("funds_future")),
                locals.set("funds_future", zero),
            ),
        )
    )

    invokations = {}

    invokations["nominate"] = tl.Seq(
        # TODO: verify if no-op can be called when not opt-in
        # tl.If(tl.Not(tl.App.optedIn()), tl.Return(zero)),
        tl.Seq(globals.load_maybe(), locals.load_maybe()),
        tl.If(
            # verify nomination can be accepted
            is_valid_nomination,
            tl.Seq(
                # move future funds into current funds for next term
                globals.inc("funds_current", globals.get("funds_future")),
                globals.set("funds_future", zero),
                # clear votes and term usage from last term
                globals.set("votes_for", zero),
                globals.set("votes_against", zero),
                # the amount used and availbale in the next term
                globals.set("term_used", zero),
                # NOTE: budget can exceed funds, as spend will be capped to votes
                globals.set("term_budget", tl.Btoi(tl.Txn.application_args[1])),
                # setup the new nomination
                globals.set("nominee", tl.Txn.sender()),
                globals.set("last_nomination_ts", timestamp),
                locals.set("last_nomination_ts", timestamp),
                tl.Return(one),
            ),
        ),
        # didn't succeed
        tl.Return(zero),
    )

    invokations["vote_for"] = tl.Seq(
        tl.Seq(globals.load_maybe(), locals.load_maybe()),
        tl.If(
            # verify vote can be accepted
            is_state_voting,
            tl.Seq(
                # clear previous vote
                remove_vote,
                # update current funds for vote
                update_funds,
                # add local votes to global tally
                globals.inc("votes_for", locals.get("funds_current")),
                # and track local vote as cast
                locals.set("votes_for", locals.get("funds_current")),
                tl.Return(one),
            ),
        ),
        tl.Return(zero),
    )

    invokations["vote_against"] = tl.Seq(
        tl.Seq(globals.load_maybe(), locals.load_maybe()),
        tl.If(
            # verify vote can be accepted
            is_state_voting,
            tl.Seq(
                # clear previous vote
                remove_vote,
                # update current funds for vote
                update_funds,
                # add local votes to global tally
                globals.inc("votes_against", locals.get("funds_current")),
                # and track local vote as cast
                locals.set("votes_against", locals.get("funds_current")),
                tl.Return(one),
            ),
        ),
        tl.Return(zero),
    )

    invokations["add_funds"] = tl.Seq(
        tl.Seq(globals.load_maybe(), locals.load_maybe()),
        tl.Seq(
            # add to funds available for future term
            globals.inc("funds_future", amount_funded),
            # shift local funds into current voting period if applicable
            update_funds,
            # add to funds for future voting period (will try to shift into
            # current before any vote)
            locals.inc("funds_future", amount_funded),
            locals.inc("last_funds_ts", timestamp),
            tl.Return(one),
        ),
    )

    # TODO: extract funds during term
    # TODO: extract additional funds (un-tracked payments) during term?
    # TODO: vouching system for account approval on opt-in

    on_create = tl.Seq(globals.create(), tl.Return(one))
    on_opt_in = tl.Seq(locals.create(), tl.Return(one))

    on_close_out = tl.Seq(
        tl.Seq(globals.load_maybe(), locals.load_maybe()),
        tl.Seq(
            remove_vote,
            update_funds,
            globals.dec("funds_current", globals.get("funds_current")),
            globals.dec("funds_future", globals.get("funds_future")),
            tl.Return(one),
        ),
    )

    return utils.new_app_info(
        on_create=on_create,
        on_opt_in=on_opt_in,
        on_close_out=on_close_out,
        on_clear=on_close_out,
        invokations=invokations,
        global_schema=globals.schema(),
        local_schema=locals.schema(),
    )

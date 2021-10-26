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


def build_distributed_treasury_app(
    voting_duration: int,
    term_duration: int,
    cooldown: int,
) -> utils.AppBuildInfo:
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

    app_address = tl.Global.current_application_address()

    cooldown = tl.Int(cooldown)
    voting_duration = tl.Int(voting_duration)
    term_duration = tl.Int(term_duration)

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

    withdrawl_amount = tl.Btoi(tl.Txn.application_args[1])
    is_valid_withdrawl = tl.And(
        is_state_term,
        tl.Txn.sender() == globals.get("nominee"),
        tl.Le(
            withdrawl_amount,
            tl.If(
                globals.get("term_budget") <= globals.get("votes_for"),
                globals.get("term_budget") - globals.get("term_used"),
                globals.get("votes_for") - globals.get("term_used"),
            ),
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

    invokations["withdraw_funds"] = tl.Seq(
        tl.Seq(globals.load_maybe(), locals.load_maybe()),
        # ensure the state is in term and the sender is the nominee
        tl.If(
            is_valid_withdrawl,
            tl.Seq(
                # sumbit an internal trasaction to the nominee for the amount
                tl.InnerTxnBuilder.Begin(),
                tl.InnerTxnBuilder.SetField(tl.TxnField.type_enum, tl.TxnType.Payment),
                tl.InnerTxnBuilder.SetField(
                    tl.TxnField.receiver, globals.get("nominee")
                ),
                tl.InnerTxnBuilder.SetField(tl.TxnField.amount, withdrawl_amount),
                tl.InnerTxnBuilder.Submit(),
                # increment the used funds in this term
                globals.inc("term_used", withdrawl_amount),
                tl.Return(one),
            ),
        ),
        tl.Return(zero),
    )

    # TODO: check for excees funds and credit them to accounts
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

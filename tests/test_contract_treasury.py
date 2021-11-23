import time
from pathlib import Path
from typing import Dict, List, NamedTuple
from unittest import TestCase

import algosdk as ag
import pyteal as tl
import pytest
from algosdk.future.transaction import (
    ApplicationClearStateTxn,
    ApplicationCloseOutTxn,
    ApplicationDeleteTxn,
    ApplicationNoOpTxn,
    ApplicationOptInTxn,
    ApplicationUpdateTxn,
    PaymentTxn,
    SuggestedParams,
)

from algorand_tut import contracts, utils

NODE_DATA_DIR = Path("/var/lib/algorand/net1/Primary")
MSG_REJECT = r".*transaction rejected by ApprovalProgram$"
MSG_ERR = r".*transaction rejected by ApprovalProgram$"


class _IsSome:
    def __eq__(self, other) -> bool:
        if other is None:
            return False
        else:
            return True


IS_SOME = _IsSome()


class Config(NamedTuple):
    algod_client: utils.AlgodClient
    kmd_client: utils.KMDClient
    accounts: List[utils.AccountInfo]


def build_cfg() -> Config:
    algod_client = utils.build_algod_client(NODE_DATA_DIR)
    kmd_client = utils.build_kmd_client(NODE_DATA_DIR)
    accounts = []
    txids = []
    for _ in range(3):
        account, txid = utils.fund_from_genesis(
            algod_client,
            kmd_client,
            ag.util.algos_to_microalgos(1000),
        )
        accounts.append(account)
        txids.append(txid)
    assert len(utils.get_confirmed_transactions(algod_client, txids, 5)) == 3
    return Config(
        algod_client=algod_client,
        kmd_client=kmd_client,
        accounts=accounts,
    )


def build_params(cfg: Config) -> SuggestedParams:
    params = cfg.algod_client.suggested_params()
    params.fee = 0
    return params


WAIT = 1


def build_app(cfg: Config, params: SuggestedParams) -> utils.AppInfo:
    app = contracts.build_distributed_treasury_app(WAIT, WAIT, WAIT)
    txn = utils.build_app_from_build_info(cfg.algod_client, app, cfg.accounts[0].address, params)
    txid = cfg.algod_client.send_transaction(txn.sign(cfg.accounts[0].key))
    return utils.build_app_info_from_result(
        utils.get_confirmed_transaction(cfg.algod_client, txid, 5)
    )


def opt_in(cfg: Config, params: SuggestedParams, app: utils.AppInfo) -> utils.AppInfo:
    txn = ApplicationOptInTxn(cfg.accounts[0].address, params, app.app_id)
    txid1 = cfg.algod_client.send_transaction(txn.sign(cfg.accounts[0].key))
    txn = ApplicationOptInTxn(cfg.accounts[1].address, params, app.app_id)
    txid2 = cfg.algod_client.send_transaction(txn.sign(cfg.accounts[1].key))
    assert (
        len(utils.get_confirmed_transactions(cfg.algod_client, [txid1, txid2], 5)) == 2
    )


def fund_treasury(cfg: Config, params: SuggestedParams, app: utils.AppInfo):
    txns = utils.group_txns(
        PaymentTxn(
            cfg.accounts[0].address,
            params,
            app.address,
            ag.util.algos_to_microalgos(10),
        ),
        ApplicationNoOpTxn(
            cfg.accounts[0].address, params, app.app_id, ["add_funds".encode("utf8")]
        ),
    )
    txns = [t.sign(cfg.accounts[0].key) for t in txns]
    txid1 = cfg.algod_client.send_transactions(txns)

    txns = utils.group_txns(
        PaymentTxn(
            cfg.accounts[1].address, params, app.address, ag.util.algos_to_microalgos(5)
        ),
        ApplicationNoOpTxn(
            cfg.accounts[1].address, params, app.app_id, ["add_funds".encode("utf8")]
        ),
    )
    txns = [t.sign(cfg.accounts[1].key) for t in txns]
    txid2 = cfg.algod_client.send_transactions(txns)

    assert (
        len(utils.get_confirmed_transactions(cfg.algod_client, [txid1, txid2], 5)) == 2
    )


class TestRejections(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = build_cfg()
        cls.params = build_params(cls.cfg)
        cls.app = build_app(cls.cfg, cls.params)
        opt_in(cls.cfg, cls.params, cls.app)

    def test_it_rejects_deletion(self):
        for account in self.cfg.accounts:
            txn = ApplicationDeleteTxn(
                sender=account.address, sp=self.params, index=self.app.app_id
            )
            with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
                self.cfg.algod_client.send_transaction(txn.sign(account.key))

    def test_it_rejects_update(self):
        program_true = utils.compile_teal(self.cfg.algod_client,
            tl.compileTeal(
                tl.Return(tl.Int(1)),
                mode=tl.Mode.Application,
                version=tl.MAX_TEAL_VERSION,
            )
        )
        for account in self.cfg.accounts:
            txn = ApplicationUpdateTxn(
                sender=account.address,
                sp=self.params,
                index=self.app.app_id,
                approval_program=program_true,
                clear_program=program_true,
            )
            with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
                self.cfg.algod_client.send_transaction(txn.sign(account.key))

    def test_it_rejects_no_opt(self):
        for account in self.cfg.accounts:
            txn = ApplicationNoOpTxn(
                sender=account.address,
                sp=self.params,
                index=self.app.app_id,
            )
            with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
                self.cfg.algod_client.send_transaction(txn.sign(account.key))

    def test_it_rejects_invalid_opt_value(self):
        for account in self.cfg.accounts:
            txn = ApplicationNoOpTxn(
                sender=account.address,
                sp=self.params,
                index=self.app.app_id,
                app_args=[b""],
            )
            with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
                self.cfg.algod_client.send_transaction(txn.sign(account.key))


class TestNomination(TestCase):
    def setUp(self):
        self.cfg = build_cfg()
        self.params = build_params(self.cfg)
        self.app = build_app(self.cfg, self.params)
        opt_in(self.cfg, self.params, self.app)
        fund_treasury(self.cfg, self.params, self.app)

    def verify_globals(self, values: Dict):
        client = self.cfg.algod_client
        app_id = self.app.app_id
        # fmt: off
        assert utils.get_app_global_key(client, app_id, "funds_current") == values.get("funds_current", 0)
        assert utils.get_app_global_key(client, app_id, "funds_future") == values.get("funds_future", 0)
        assert utils.get_app_global_key(client, app_id, "votes_for") == values.get("votes_for", 0)
        assert utils.get_app_global_key(client, app_id, "votes_against") == values.get("votes_against", 0)
        assert utils.get_app_global_key(client, app_id, "term_used") == values.get("term_used", 0)
        assert utils.get_app_global_key(client, app_id, "term_budget") == values.get("term_budget", 0)
        assert utils.get_app_global_key(client, app_id, "nominee") == values.get("nominee", None)
        assert utils.get_app_global_key(client, app_id, "last_nomination_ts") == values.get("last_nomination_ts", None)
        # fmt: on

    def verify_locals(self, address: str, values: Dict):
        client = self.cfg.algod_client
        app_id = self.app.app_id
        # fmt: off
        assert utils.get_app_local_key(client, app_id, address, "funds_current") == values.get("funds_current", 0)
        assert utils.get_app_local_key(client, app_id, address, "funds_future") == values.get("funds_future", 0)
        assert utils.get_app_local_key(client, app_id, address, "votes_for") == values.get("votes_for", 0)
        assert utils.get_app_local_key(client, app_id, address, "votes_against") == values.get("votes_against", 0)
        assert utils.get_app_local_key(client, app_id, address, "last_nomination_ts") == values.get("last_nomination_ts", None)
        assert utils.get_app_local_key(client, app_id, address, "last_vote_ts") == values.get("last_vote_ts", None)
        assert utils.get_app_local_key(client, app_id, address, "last_funds_ts") == values.get("last_funds_ts", None)
        # fmt: on

    def test_opt_in_and_fund_state(self):
        self.verify_globals({"funds_future": ag.util.algos_to_microalgos(15)})
        self.verify_locals(
            self.cfg.accounts[0].address,
            {"funds_future": ag.util.algos_to_microalgos(10), "last_funds_ts": IS_SOME},
        )
        self.verify_locals(
            self.cfg.accounts[1].address,
            {"funds_future": ag.util.algos_to_microalgos(5), "last_funds_ts": IS_SOME},
        )

    def test_opted_in_can_nominate(self):
        txn = ApplicationNoOpTxn(
            sender=self.cfg.accounts[1].address,
            sp=self.params,
            index=self.app.app_id,
            app_args=["nominate".encode("utf8"), 20],
        )
        txid = self.cfg.algod_client.send_transaction(
            txn.sign(self.cfg.accounts[1].key)
        )
        assert utils.get_confirmed_transaction(self.cfg.algod_client, txid, 5)

        self.verify_globals(
            {
                "funds_current": ag.util.algos_to_microalgos(15),
                "nominee": IS_SOME,
                "term_budget": 20,
                "last_nomination_ts": IS_SOME,
            }
        )
        self.verify_locals(
            self.cfg.accounts[0].address,
            {"funds_future": ag.util.algos_to_microalgos(10), "last_funds_ts": IS_SOME},
        )
        self.verify_locals(
            self.cfg.accounts[1].address,
            {
                "funds_future": ag.util.algos_to_microalgos(5),
                "last_nomination_ts": IS_SOME,
                "last_funds_ts": IS_SOME,
            },
        )

    def test_not_opted_in_cant_nominate(self):
        txn = ApplicationNoOpTxn(
            sender=self.cfg.accounts[2].address,
            sp=self.params,
            index=self.app.app_id,
            app_args=["nominate".encode("utf8"), 20],
        )
        with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
            self.cfg.algod_client.send_transaction(txn.sign(self.cfg.accounts[2].key))

    def test_cant_nominate_during_voting_or_term(self):
        txn = ApplicationNoOpTxn(
            sender=self.cfg.accounts[0].address,
            sp=self.params,
            index=self.app.app_id,
            app_args=["nominate".encode("utf8"), 20],
        )
        txid = self.cfg.algod_client.send_transaction(
            txn.sign(self.cfg.accounts[0].key)
        )
        assert utils.get_confirmed_transaction(self.cfg.algod_client, txid, 5)
        # there is a nominee
        assert utils.get_app_global_key(
            self.cfg.algod_client, self.app.app_id, "nominee"
        )
        time_vote = time.time()

        # can't nominate during voting
        txn = ApplicationNoOpTxn(
            sender=self.cfg.accounts[1].address,
            sp=self.params,
            index=self.app.app_id,
            app_args=["nominate".encode("utf8"), 20],
        )
        with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
            txid = self.cfg.algod_client.send_transaction(
                txn.sign(self.cfg.accounts[1].key)
            )
        
        # can't nominate during term
        time.sleep(max(0, WAIT - (time.time() - time_vote)))
        txn = ApplicationNoOpTxn(
            sender=self.cfg.accounts[1].address,
            sp=self.params,
            index=self.app.app_id,
            app_args=["nominate".encode("utf8"), 20],
        )
        with pytest.raises(ag.error.AlgodHTTPError, match=MSG_REJECT):
            txid = self.cfg.algod_client.send_transaction(
                txn.sign(self.cfg.accounts[1].key)
            )

        # can nominate after term
        time.sleep(max(0, 2 * WAIT - (time.time() - time_vote)))
        txn = ApplicationNoOpTxn(
            sender=self.cfg.accounts[1].address,
            sp=self.params,
            index=self.app.app_id,
            app_args=["nominate".encode("utf8"), 20],
        )
        txid = self.cfg.algod_client.send_transaction(
            txn.sign(self.cfg.accounts[1].key)
        )

    def test_cant_spend_outside_term(self):
        pass

    def test_nominee_can_spend_budget_during_term(self):
        pass

    def test_nominee_can_spend_budget_during_term(self):
        pass

    def test_votes_against_end_voting_no_term(self):
        pass

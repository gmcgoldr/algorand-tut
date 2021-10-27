from pathlib import Path
from typing import List, NamedTuple
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
    SuggestedParams,
)

from algorand_tut import contracts, utils

NODE_DATA_DIR = Path("/var/lib/algorand/net1/Primary")
MSG_REJECT = r".*transaction rejected by ApprovalProgram$"


class Config(NamedTuple):
    algod_client: utils.AlgodClient
    kmd_client: utils.KMDClient
    accounts: List[utils.AccountInfo]


def build_cfg():
    algod_client = utils.build_algod_client(NODE_DATA_DIR)
    kmd_client = utils.build_kmd_client(NODE_DATA_DIR)
    accounts = []
    txids = []
    for _ in range(3):
        account, txid = utils.fund_from_genesis(
            algod_client,
            kmd_client,
            ag.util.algos_to_microalgos(100),
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


def build_app(cfg: Config, params: SuggestedParams) -> utils.AppInfo:
    app = contracts.build_distributed_treasury_app(10, 10, 10)
    txn = utils.build_app_from_build_info(app, cfg.accounts[0].address, params)
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
        program_true = utils.compile_teal_source(
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

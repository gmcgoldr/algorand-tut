import base64
from typing import NamedTuple
from unittest.mock import Mock

import algosdk as ag
import pyteal as tl
import pytest
from algosdk.future.transaction import StateSchema

from algorand_tut import utils


class AccountInfo(NamedTuple):
    key: str
    address: str


def test_get_wallet_id_returns_id():
    client = Mock()
    client.list_wallets = lambda: [
        {"name": "a", "id": "id_a"},
        {"name": "b", "id": "id_b"},
    ]
    assert utils.get_wallet_id(client, "b") == "id_b"


def test_get_wallet_id_returns_none():
    client = Mock()
    client.list_wallets = lambda: [{"name": "a", "id": "id_a"}, {"name": "b"}]
    assert utils.get_wallet_id(client, "b") is None
    assert utils.get_wallet_id(client, "c") is None


def test_get_wallet_handle_inits_and_releases():
    client = Mock()
    client.init_wallet_handle = lambda *_: "handle"
    with utils.get_wallet_handle(client, "id", "password") as handle:
        assert handle == "handle"
    client.release_wallet_handle.assert_called_once_with("handle")


def test_fix_lease_size_pads_lease():
    fixed = utils.fix_lease_size(b"abc")
    assert len(fixed) == ag.constants.LEASE_LENGTH
    assert fixed[:3] == b"abc"
    assert all([b == 0 for b in fixed[3:]])


def test_fix_lease_size_truncates_lease():
    fixed = utils.fix_lease_size(b"a" * (ag.constants.LEASE_LENGTH + 1))
    assert len(fixed) == ag.constants.LEASE_LENGTH


def test_build_app_info_from_result():
    result = {"application-index": 0}
    app = utils.build_app_info_from_result(result)
    assert app.app_id == 0
    assert app.address == "6X7XJO6FX3SHUK2OUL46QBQDSNO67RAFK6O73KJD4IVOMTSOIYANOIVWNU"


class TestNewAppInfo:
    def test_it_branches_for_on_completion_codes(self):
        info = utils.new_app_info(
            on_create=tl.Return(tl.Int(2)),
            on_delete=tl.Return(tl.Int(3)),
            on_update=tl.Return(tl.Int(4)),
            on_opt_in=tl.Return(tl.Int(5)),
            on_close_out=tl.Return(tl.Int(6)),
            on_clear=tl.Return(tl.Int(7)),
            invokations=None,
            global_schema=StateSchema(),
            local_schema=StateSchema(),
        )
        # fmt: off
        assert str(info.approval) == (
            '(Cond '
                '['
                    '(== (Txn ApplicationID) (Int: 0)), '
                    '(Return (Int: 2))'
                '] '
                '['
                    '(== (Txn OnCompletion) (IntEnum: DeleteApplication)), '
                    '(Return (Int: 3))'
                '] '
                '['
                    '(== (Txn OnCompletion) (IntEnum: UpdateApplication)), '
                    '(Return (Int: 4))'
                '] '
                '['
                    '(== (Txn OnCompletion) (IntEnum: OptIn)), '
                    '(Return (Int: 5))'
                '] '
                '['
                    '(== (Txn OnCompletion) (IntEnum: CloseOut)), '
                    '(Return (Int: 6))'
                '] '
                '[(Int: 1), (Return (Int: 0))]'
            ')'
        )
        # fmt: on
        assert str(info.clear) == "(Return (Int: 7))"

    def test_it_branches_for_invokations(self):
        info = utils.new_app_info(
            on_create=None,
            on_delete=None,
            on_update=None,
            on_opt_in=None,
            on_close_out=None,
            on_clear=None,
            invokations={"name": tl.Return(tl.Int(2))},
            global_schema=StateSchema(),
            local_schema=StateSchema(),
        )
        # fmt: off
        assert str(info.approval) == (
            '(Cond '
                '['
                    '(&& '
                        '(== (Txn OnCompletion) (IntEnum: NoOp)) '
                        '(If '
                            '(>= (Txn NumAppArgs) (Int: 1)) '
                            '(== (Txna ApplicationArgs 0) (utf8 bytes: "name")) '
                            '(Int: 0)'
                        ')'
                    '), '
                    '(Return (Int: 2))'
                '] '
                '[(Int: 1), (Return (Int: 0))]'
            ')'
        )
        # fmt: on

    def test_it_sets_schema(self):
        global_schema = StateSchema(num_uints=1)
        local_schema = StateSchema(num_byte_slices=2)
        info = utils.new_app_info(
            on_create=tl.Return(tl.Int(1)),
            on_delete=None,
            on_update=None,
            on_opt_in=None,
            on_close_out=None,
            on_clear=None,
            invokations=None,
            global_schema=global_schema,
            local_schema=local_schema,
        )
        assert info.global_schema is global_schema
        assert info.local_schema is local_schema


@pytest.fixture
def state() -> utils.StateBuilder:
    return utils.StateBuilder(
        utils.StateBuilder.Scope.GLOBAL,
        [
            utils.KeyInfo("def_i", tl.Int, tl.Int(1)),
            utils.KeyInfo("def_b", tl.Bytes, tl.Bytes("a")),
            utils.KeyInfo("opt_i", tl.Int),
            utils.KeyInfo("opt_b", tl.Bytes),
        ],
    )


class TestStateBuilder:
    def test_it_counts_schema(self):
        state = utils.StateBuilder(
            utils.StateBuilder.Scope.GLOBAL,
            [
                utils.KeyInfo("a", tl.Bytes),
                utils.KeyInfo("b", tl.Int),
                utils.KeyInfo("c", tl.Int),
                utils.KeyInfo("d", tl.Int),
                utils.KeyInfo("e", tl.Bytes),
            ],
        )
        assert state.schema().num_byte_slices == 2
        assert state.schema().num_uints == 3

    def test_it_gets_default_value(self, state: utils.StateBuilder):
        assert str(state.get("def_i")) == '(app_global_get (utf8 bytes: "def_i"))'

    def test_it_loads_and_gets_opt_value(self, state: utils.StateBuilder):
        assert str(state.maybe("opt_b")).startswith(
            "("
            '(app_global_get_ex (Global CurrentApplicationID) (utf8 bytes: "opt_b")) '
            "(StackStore slot#"
        )
        assert str(state.get("opt_b")).startswith("(Load slot#")

    def test_it_sets_int(self, state: utils.StateBuilder):
        assert (
            str(state.set("def_i", tl.Int(2)))
            == '(app_global_put (utf8 bytes: "def_i") (Int: 2))'
        )
        assert (
            str(state.set("opt_i", tl.Int(2)))
            == '(app_global_put (utf8 bytes: "opt_i") (Int: 2))'
        )

    def test_it_sets_bytes(self, state: utils.StateBuilder):
        assert (
            str(state.set("def_b", tl.Bytes("b")))
            == '(app_global_put (utf8 bytes: "def_b") (utf8 bytes: "b"))'
        )
        assert (
            str(state.set("opt_b", tl.Bytes("b")))
            == '(app_global_put (utf8 bytes: "opt_b") (utf8 bytes: "b"))'
        )

    def test_it_increments(self, state: utils.StateBuilder):
        assert str(state.inc("def_i", tl.Int(2))) == (
            '(app_global_put (utf8 bytes: "def_i") '
            '(+ (app_global_get (utf8 bytes: "def_i")) (Int: 2)))'
        )

    def test_it_decrements(self, state: utils.StateBuilder):
        assert str(state.dec("def_i", tl.Int(2))) == (
            '(app_global_put (utf8 bytes: "def_i") '
            '(- (app_global_get (utf8 bytes: "def_i")) (Int: 2)))'
        )

    def test_it_builds_create(self, state: utils.StateBuilder):
        # fmt: off
        assert str(state.create()) == (
            '(Seq '
                '(app_global_put (utf8 bytes: "def_i") (Int: 1)) '
                '(app_global_put (utf8 bytes: "def_b") (utf8 bytes: "a"))'
            ')'
        )
        # fmt: on

    def test_it_builds_load_maybe(self, state: utils.StateBuilder):
        teal = str(state.load_maybe())
        # the actual code has arbitrary slot numbers, just ensure it has the
        # correct elements
        assert '"opt_i"' in teal
        assert '"opt_b"' in teal
        assert "app_global_get_ex" in teal


def test_get_app_global_key_returns_value():
    client = Mock()
    key = base64.b64encode("a".encode("utf8")).decode("ascii")
    client.application_info = (
        lambda app_id: {
            "params": {
                "global-state": [
                    {"key": ""},
                    {},
                    {"key": key, "value": {"type": 1, "bytes": b"b"}},
                ]
            }
        }
        if app_id == 1
        else {}
    )
    assert utils.get_app_global_key(client, app_id=1, key="a") == b"b"


def test_get_app_global_key_missing_returns_none():
    client = Mock()
    key = base64.b64encode("a".encode("utf8")).decode("ascii")
    client.application_info = (
        lambda app_id: {
            "params": {
                "global-state": [
                    {"key": ""},
                    {},
                    {"key": key, "value": {"type": 1, "bytes": b"b"}},
                ]
            }
        }
        if app_id == 1
        else {}
    )
    assert utils.get_app_global_key(client, app_id=1, key="") is None
    assert utils.get_app_global_key(client, app_id=0, key="b") is None


def test_get_app_local_key_returns_value():
    client = Mock()
    key = base64.b64encode("a".encode("utf8")).decode("ascii")
    client.account_info = (
        lambda address: {
            "apps-local-state": [
                {
                    "id": 1,
                    "key-value": [
                        {"key": ""},
                        {},
                        {"key": key, "value": {"type": 1, "bytes": b"c"}},
                    ],
                }
            ]
        }
        if address == "b"
        else {}
    )
    assert utils.get_app_local_key(client, app_id=1, address="b", key="a") == b"c"


def test_get_app_local_key_missing_returns_none():
    client = Mock()
    key = base64.b64encode("a".encode("utf8")).decode("ascii")
    client.account_info = (
        lambda address: {
            "apps-local-state": [
                {
                    "id": 1,
                    "key-value": [
                        {"key": ""},
                        {},
                        {"key": key, "value": {"type": 1, "bytes": b"c"}},
                    ],
                }
            ]
        }
        if address == "b"
        else {}
    )
    assert utils.get_app_local_key(client, app_id=0, address="b", key="a") == None
    assert utils.get_app_local_key(client, app_id=1, address="", key="a") == None
    assert utils.get_app_local_key(client, app_id=1, address="b", key="") == None


def test_extract_state_value_returns_value():
    assert utils.extract_state_value({"type": 1, "bytes": b"a", "uint": None}) == b"a"
    assert utils.extract_state_value({"type": 2, "bytes": b"", "uint": 1}) == 1

from pathlib import Path
from typing import NamedTuple, List
from unittest.mock import Mock

import algosdk as ag
import pyteal as tl

from algorand_tut import utils

NODE_DATA_DIR = Path("/var/lib/algorand/net1/Primary")


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


class TestNewAppInfo:
    def test_it_builds_default_create_delete(self):
        info = utils.new_app_info()
        app = tl.compileTeal(info.approval, mode=tl.Mode.Application, version=5)

        assert info.global_schema.num_uints is None
        assert info.global_schema.num_byte_slices is None
        assert info.local_schema.num_uints is None
        assert info.local_schema.num_byte_slices is None

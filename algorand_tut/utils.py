import base64
import subprocess
import sys
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, NamedTuple, Tuple, Union

import algosdk as ag
import pyteal as tl
from algosdk.future import transaction
from algosdk.future.transaction import PaymentTxn
from algosdk.kmd import KMDClient
from algosdk.v2client.algod import AlgodClient

ZERO_ADDRESS = ag.encoding.encode_address(bytes(32))


def build_algod_client(data_dir: Path) -> AlgodClient:
    # Read `algod` network information from the node data directory.
    algod_address = (data_dir / "algod.net").read_text().strip()
    algod_token = (data_dir / "algod.token").read_text().strip()
    algod_client = AlgodClient(
        algod_address=f"http://{algod_address}", algod_token=algod_token
    )
    return algod_client


def build_kmd_client(data_dir: Path, version: str = "0.5") -> KMDClient:
    # Read `kmd` network information from the node's kmd directory.
    # NOTE: this can be read only by the `algorand` user, so this script needs
    # to be invoked as that user. Otherwise it's possible to prompt the user
    # for this information, and have the user read the information.
    kmd_address = (data_dir / f"kmd-v{version}" / "kmd.net").read_text().strip()
    kmd_token = (data_dir / f"kmd-v{version}" / "kmd.token").read_text().strip()
    kmd_client = KMDClient(kmd_address=f"http://{kmd_address}", kmd_token=kmd_token)
    return kmd_client


def get_wallet_id(kmd_client: KMDClient, name: str) -> str:
    """
    Get the ID of the wallet of a given name from the `kmd`.

    Args:
        kmd_client: the `kmd` client to query
        name: the wallet name

    Returns:
        the wallet ID in `kmd` or `None` if it is not found
    """
    wallets = {w["name"]: w for w in kmd_client.list_wallets()}
    wallet_id = wallets.get(name, {}).get("id", None)
    return wallet_id


@contextmanager
def get_wallet_handle(client: KMDClient, wallet_id: str, password: str) -> str:
    """
    Get the `kmd` to initialize a wallet handle, and release it when the
    context is closed.

    Args:
        client: the client connected to the node's `kmd`
        wallet_id: the wallet id
        password: the wallet password
    """
    handle = client.init_wallet_handle(wallet_id, password)
    yield handle
    client.release_wallet_handle(handle)


def get_confirmed_transactions(
    client: AlgodClient, transaction_ids: List[int], timeout_blocks: int
) -> Dict:
    """
    Wait for the network to confirm a transactions and return their
    information.

    Args:
        client: the client connected to the node
        transaction_ids: list of transactions for which to retreive info
        timeout: raise an error if no confirmation is received after this
            many blocks
    """
    start_round = client.status()["last-round"] + 1
    current_round = start_round
    waiting_ids = set(transaction_ids)
    confirmed = []

    while waiting_ids and current_round < start_round + timeout_blocks:
        for transaction_id in list(waiting_ids):
            # NOTE: documentation suggests that transactions are "remembered"
            # by a node for some time after confirmation, but doesn't specify
            # how long
            pending_txn = client.pending_transaction_info(transaction_id)
            if pending_txn["pool-error"]:
                waiting_ids.remove(transaction_id)
            elif pending_txn.get("confirmed-round", 0) > 0:
                confirmed.append(pending_txn)
                waiting_ids.remove(transaction_id)
        # wait until the end of this block
        client.status_after_block(current_round)
        current_round += 1

    return confirmed


def get_confirmed_transaction(
    client: AlgodClient, transaction_id: int, timeout_blocks: int
) -> Dict:
    """
    See `get_confirmed_transactions`, but for a single transaction id.
    """
    confirmed = get_confirmed_transactions(client, [transaction_id], timeout_blocks)
    if confirmed:
        return confirmed[0]
    else:
        return None


def compile_teal_source(source: str) -> bytes:
    """
    Compile teal source code into a teal binary using `goal`.

    Writes intermediate files to a temporary directory and makes a subprocess
    call to `goal`.

    If the compilation fails, prints the output and rasies an error.

    Args:
        source: the teal source code

    Returns:
        the teal program binary
    """
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        with (tmpdir / "program.teal").open("w") as fio:
            fio.write(source)

        args = [
            "goal",
            "clerk",
            "compile",
            "-o",
            str(tmpdir / "program.tealc"),
            str(tmpdir / "program.teal"),
        ]
        result = subprocess.run(args, check=True, capture_output=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            sys.stderr.flush()
            # raise an error
            result.check_returncode()

        with (tmpdir / "program.tealc").open("rb") as fio:
            return fio.read()


def fix_lease_size(lease: bytes) -> bytes:
    """
    Given a string of bytes to use as a lease, right pad with 0s to get the
    correct number of bytes.
    """
    lease = lease[: ag.constants.LEASE_LENGTH]
    lease = lease + (b"\x00" * max(0, ag.constants.LEASE_LENGTH - len(lease)))
    return lease


class AccountInfo(NamedTuple):
    key: str
    address: str


def fund_from_genesis(
    algod_client: AlgodClient, kmd_client: KMDClient, amount: int
) -> Tuple[AccountInfo, str]:
    """
    Create a new account and fund it from the account that received the gensis
    funds.

    Expects an unencrypted wallet "unencrypted-default-wallet" whose first key
    is the address of the account with the genesis funds.

    Args:
        algod_client: client to send node commands to
        kmd_client: client to use in signing the transaction
        amount: the quantity of microAlgos to fund

    Returns:
        the private key and address of the newly funded account
    """
    wallet_id = get_wallet_id(kmd_client, "unencrypted-default-wallet")

    # Get the address of the source account with all the genesis tokens
    with get_wallet_handle(kmd_client, wallet_id, "") as handle:
        keys = kmd_client.list_keys(handle)
        if not keys:
            raise RuntimeError("funded account not found in wallet")
        sender_address = keys[0]

    key, address = ag.account.generate_account()

    # Transfer algos to the escrow account
    params = algod_client.suggested_params()
    params.fee = 0  # use the minimum network fee
    txn = PaymentTxn(sender=sender_address, sp=params, receiver=address, amt=amount)
    # Sign with the sender account keys, managed by its wallet
    with get_wallet_handle(kmd_client, wallet_id, "") as handle:
        txn = kmd_client.sign_transaction(handle, "", txn)
    txid = algod_client.send_transaction(txn)

    return AccountInfo(key, address), txid


class AppInfo(NamedTuple):
    app_id: str
    address: str


def build_app_info_from_result(result: Dict) -> AppInfo:
    app_id = result.get("application-index", None)
    if app_id is None:
        return None
    address = ag.encoding.encode_address(
        ag.encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
    )
    return AppInfo(app_id=app_id, address=address)


def group_txns(*txns: transaction.Transaction) -> List[transaction.Transaction]:
    gid = transaction.calculate_group_id(txns)
    for txn in txns:
        txn.group = gid
    return txns


class AppBuildInfo(NamedTuple):
    """Data required to build a stateful contract (app)."""

    approval: tl.Expr
    clear: tl.Expr
    global_schema: transaction.StateSchema
    local_schema: transaction.StateSchema


def build_app_from_build_info(
    info: AppBuildInfo, address: str, params: transaction.SuggestedParams
) -> transaction.ApplicationCreateTxn:
    """
    Compile the app programs build the app creation transaction.
    """
    return transaction.ApplicationCreateTxn(
        # this will be the app creator
        sender=address,
        sp=params,
        # no state change requested in this transaciton beyond app creation
        on_complete=transaction.OnComplete.NoOpOC.real,
        # the program to handle app state changes
        approval_program=compile_teal_source(
            tl.compileTeal(
                info.approval,
                mode=tl.Mode.Application,
                version=tl.MAX_TEAL_VERSION,
            )
        ),
        # the program to run when an account forces an opt-out
        clear_program=compile_teal_source(
            tl.compileTeal(
                info.clear,
                mode=tl.Mode.Application,
                version=tl.MAX_TEAL_VERSION,
            )
        ),
        # the amount of storage used by the app
        global_schema=info.global_schema,
        local_schema=info.local_schema,
    )


def new_app_info(
    on_create: tl.Expr,
    on_delete: tl.Expr,
    on_update: tl.Expr,
    on_opt_in: tl.Expr,
    on_close_out: tl.Expr,
    on_clear: tl.Expr,
    invokations: Dict[str, tl.Expr],
    global_schema: transaction.StateSchema,
    local_schema: transaction.StateSchema,
) -> AppBuildInfo:
    """
    Build the program data required for an app to execute the provided
    expressions, with the provided storage schema.

    Of the transaction-invoked state changes (e.g. opt-in, update etc.), only
    those with a provided expression are permitted, and only when that
    expression returns one. Note that creation executes only when the app is
    not initialized, and the trasaction is no-op.

    Additional state changes to the app's storage can be invoked by passing a
    string as the first argument. In that case, if there is a corresponding
    name in the `invokations` list, then it's expression will be evaluated, and
    if it returns one, then any state changes carried out will be committed.

    Args:
        on_create: expression to invoke if the application is not initialized
        on_delete: expression to invoke for deletion
        on_update: expression to invoke for update
        on_opt_in: expression to invoke for opt in
        on_close_out: expression to invoke for close out (opt out)
        on_clear: expression to invoke for clear (forced opt out)
        invokations: mapping of invokation name to expression
        global_schema: global storage schema
        local_schema: local storage schema
    """
    zero = tl.Int(0)
    one = tl.Int(1)

    # Each branch is a pair of expressions: one which tests if the branch
    # should be executed, and another which is the branche's logic. If the
    # branch logic returns 0, then the app state is unchanged, no matter what
    # operations were performed during its exectuion (i.e. it rolls back). Only
    # the first matched branch is executed.
    branches = []

    # handle `OnComplete` enum values
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
    if on_opt_in:
        branches.append([tl.Txn.on_completion() == tl.OnComplete.OptIn, on_opt_in])
    if on_close_out:
        branches.append(
            [tl.Txn.on_completion() == tl.OnComplete.CloseOut, on_close_out]
        )

    # handle custon invokations with named arg
    invokations = {} if invokations is None else invokations
    for name, expr in invokations.items():
        branches.append(
            [
                # use a an invokation branch for no-op calls with the branch
                # name as arg 0
                tl.And(
                    tl.Txn.on_completion() == tl.OnComplete.NoOp,
                    # don't want to err if arg is not provided, so use if
                    tl.If(tl.Txn.application_args.length() >= one)
                    .Then(tl.Txn.application_args[0] == tl.Bytes(name))
                    .Else(zero),
                ),
                expr,
            ]
        )

    # fallthrough: if no branch is selected, reject
    branches.append([one, tl.Return(zero)])

    return AppBuildInfo(
        # build the conditional branching
        approval=tl.Cond(*branches),
        # the clear program is separate
        clear=on_clear,
        global_schema=global_schema,
        local_schema=local_schema,
    )


class KeyInfo(NamedTuple):
    """
    Information about an app state key.

    The `key` is used to identify a stateful variable in an app. It's type is
    given in `has_type`.

    If `init` is provided, then this key should be added to the app by default
    on cosntruction, with the `init` value. Otherwise, the key might not be
    present in the app, so it can be accessed as a `MaybeValue`.

    It is up to the app program to:
    1) use `StateBuilder.create` to create the keys when an app is constructed,
    2) use `StateBuilder.load_maybe` to store `MaybeValue` keys before
       accessing their values
    """

    key: str
    has_type: Union[tl.Int, tl.Bytes]
    init: Union[tl.Int, tl.Bytes] = None


class StateBuilder:
    """Tracks an app's state and provides methods for accessing it."""

    class Scope(Enum):
        GLOBAL = 0
        LOCAL = 1

    def __init__(
        self,
        scope: Scope,
        key_infos: List[KeyInfo],
        app_id: tl.Expr = None,
        account_id: tl.Expr = None,
    ):
        """
        Prepare a collection of state keys for some scope.

        Keys with an `init` field will be treated as optional, meaning that
        they can be accessed with the `maybe` method, and will not be set in
        the `create` method. In order to access their values they must first
        be loaded into slots using the `load_maybe` method.

        The `scope` can be either `Scope.GLOBAL` or `Scope.LOCAL`. For a local
        scope, this will interact with keys of the current transaction sender,
        or of the account `account_id` if provided.

        By default, the scope is for the current application. However, if an
        `app_id` is provided, this will be used to interact with the state of
        another app (in which case none of the keys can have the `init` field
        as none are known to exist).
        """
        self.scope = scope
        self.account_id = account_id if account_id is not None else tl.Txn.sender()

        is_foreign = app_id is not None
        app_id = app_id if app_id is not None else tl.App.id()

        # map keys to info
        self.infos: Dict[str, KeyInfo] = {}
        # map key to its bytes respresentation
        self.bytes: Dict[str, tl.Bytes] = {}
        # expressions to load keys that are in the state (has init)
        self.loader: Dict[str, tl.App] = {}
        # expressions to load the keys that might be in the state (no init)
        self.loader_ex: Dict[str, tl.MaybeValue] = {}
        self.setter: Dict[str, tl.App] = {}

        for info in key_infos:
            key = info.key
            # currently keys are limited to 64 bytes
            if len(key.encode("utf8")) > 64:
                raise ValueError(f"key too long: {key}")
            if is_foreign and info.init is not None:
                raise ValueError(f"key cannot have init into foreign app")

            key_bytes = tl.Bytes(key)
            self.bytes[key] = key_bytes
            self.infos[key] = info

            # cache the loader expressions for global state
            if scope is StateBuilder.Scope.GLOBAL:
                if info.init is None:
                    # NOTE: this is a `MaybeValue` which tracks the stored slot
                    # so the object must be re-used between loading and
                    # accessing the value, hence this has to be cached
                    self.loader_ex[key] = tl.App.globalGetEx(app_id, key_bytes)
                else:
                    # this is just an expression, it doesn't need to be cached
                    # but this way the interface is kept consistent
                    self.loader[key] = tl.App.globalGet(key_bytes)

            # cache the loader expressions for local state
            elif scope is StateBuilder.Scope.LOCAL:
                if info.init is None:
                    self.loader_ex[key] = tl.App.localGetEx(
                        self.account_id, app_id, key_bytes
                    )
                else:
                    self.loader[key] = tl.App.localGet(self.account_id, key_bytes)

    def get(self, key: str) -> tl.Expr:
        """Build the expression to get the state value at `key`"""
        loader = self.loader.get(key, None)
        if loader is not None:
            return loader
        loader = self.loader_ex.get(key, None)
        if loader is not None:
            return loader.value()
        raise KeyError(key)

    def maybe(self, key: str) -> tl.MaybeValue:
        """
        Get the `MaybeValue` object for `key`.

        The object itself is an expression to load the value into a slot. It
        also has members for accessing that value, based on the slot
        information.

        Thus, before using the expression `MaybeValue.load`, the `MaybeValue`
        expression must be evaluated to store it into the slot.
        """
        loader = self.loader_ex[key]
        return loader

    def set(self, key: str, value: Union[tl.Int, tl.Bytes]) -> tl.Expr:
        """Build the expression to set the state value at `key`"""
        key_bytes = self.bytes[key]
        if self.scope is StateBuilder.Scope.GLOBAL:
            return tl.App.globalPut(key_bytes, value)
        elif self.scope is StateBuilder.Scope.LOCAL:
            return tl.App.localPut(self.account_id, key_bytes, value)

    def inc(self, key: str, value: Union[tl.Int, tl.Bytes]) -> tl.Expr:
        """
        Build the expression to increment the state value at `key` by `value`.
        """
        return self.set(key, self.get(key) + value)

    def dec(self, key: str, value: Union[tl.Int, tl.Bytes]) -> tl.Expr:
        """
        Build the expression to decrement the state value at `key` by `value`.
        """
        return self.set(key, self.get(key) - value)

    def create(self) -> tl.Expr:
        """
        Build the expression to set the initial state values for those keys
        with an `init` field.
        """
        setters = []
        for key, info in self.infos.items():
            if info.init is None:
                continue
            if self.scope is StateBuilder.Scope.GLOBAL:
                setters.append(tl.App.globalPut(self.bytes[key], info.init))
            elif self.scope is StateBuilder.Scope.LOCAL:
                setters.append(
                    tl.App.localPut(self.account_id, self.bytes[key], info.init)
                )
        return tl.Seq(*setters)

    def load_maybe(self) -> tl.Expr:
        """
        Build the expression to run over those keys without an `init` field and
        build their `MaybeValue` expressions to store them in slots.
        """
        return tl.Seq(*self.loader_ex.values())

    def schema(self) -> transaction.StateSchema:
        """Build the schema for this state."""
        num_uints = 0
        num_byte_slices = 0

        for info in self.infos.values():
            if info.has_type is tl.Int:
                num_uints += 1
            elif info.has_type is tl.Bytes:
                num_byte_slices += 1

        return transaction.StateSchema(
            num_uints=num_uints, num_byte_slices=num_byte_slices
        )


def get_app_global_key(algod_client: AlgodClient, app_id: int, key: str):
    """
    Return the value for the given `key` in `app_id`'s global data.
    """
    key = base64.b64encode(key.encode("utf8")).decode("ascii")
    app_info = algod_client.application_info(app_id)
    for key_state in app_info.get("params", {}).get("global-state", []):
        if key_state.get("key", None) != key:
            continue
        return key_state.get("value", None)
    return None


def get_app_local_key(algod_client: AlgodClient, app_id: int, address: str, key: str):
    """
    Return the value for the given `key` in `app_id`'s local data for account
    `address`.
    """
    key = base64.b64encode(key.encode("utf8")).decode("ascii")
    account_info = algod_client.account_info(address)
    for app_state in account_info.get("apps-local-state", []):
        if app_state.get("id", None) != app_id:
            continue
        for key_state in app_state.get("key-value", []):
            if key_state.get("key", None) != key:
                continue
            return key_state.get("value", None)
    return None


def extract_state_value(value: Dict):
    if value is None:
        return None
    if value.get("type", None) == 1:
        return value.get("bytes", None)
    if value.get("type", None) == 2:
        return value.get("uint", None)

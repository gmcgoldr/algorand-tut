import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict

import algosdk as ag
from algosdk.kmd import KMDClient
from algosdk.v2client.algod import AlgodClient


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


def get_confirmed_transaction(
    client: AlgodClient, transaction_id: int, timeout_blocks: int
) -> Dict:
    """
    Wait for the network to confirm a transaction and return its information.

    Args:
        client: the client connected to the node
        transaction_id: the transaction id
        timeout: raise an error if no confirmation is received after this
            many blocks
    """
    start_round = client.status()["last-round"] + 1
    current_round = start_round

    while current_round < start_round + timeout_blocks:
        # get the transaction status and return if confirmed
        pending_txn = client.pending_transaction_info(transaction_id)

        if pending_txn.get("confirmed-round", 0) > 0:
            return pending_txn
        elif pending_txn["pool-error"]:
            raise RuntimeError(pending_txn["pool_error"])

        # wait until the end of this block
        client.status_after_block(current_round)
        current_round += 1

    raise RuntimeError(f"no confirmation after {timeout_blocks} blocks")


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

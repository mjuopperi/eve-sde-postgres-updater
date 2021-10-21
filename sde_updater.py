import os
import contextlib
import tempfile
import subprocess
from bz2 import BZ2File
from typing import Optional

from dateutil import parser
from datetime import datetime, timezone
import httpx
from tqdm import tqdm


UPDATE_TIMESTAMP_LOG = ".update.log"


def _last_line_in_file(file_path) -> Optional[str]:
    if not os.path.isfile(file_path):
        return None

    # https://stackoverflow.com/a/54278929
    with open(file_path, "rb") as f:
        try:  # catch OSError in case of a one line file
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)

        last_line = f.readline().decode().strip()
        return last_line if last_line else None


def get_last_update_timestamp() -> datetime:
    date_from_log = _last_line_in_file(UPDATE_TIMESTAMP_LOG)
    if not date_from_log:
        # File does not exist or is empty
        return datetime(2003, 5, 6, tzinfo=timezone.utc)
    return parser.parse(date_from_log).replace(tzinfo=timezone.utc)


def set_update_timestamp() -> None:
    with open(UPDATE_TIMESTAMP_LOG, mode="a") as update_log:
        timestamp = datetime.utcnow().isoformat()
        update_log.write(f"{timestamp}\n")


def get_dump_timestamp() -> datetime:
    res = httpx.head(os.getenv("DB_DUMP_URL"))
    last_modified_header = res.headers.get("Last-Modified")
    if not last_modified_header:
        raise Exception("Last-Modified header missing.")
    return parser.parse(last_modified_header)


def is_out_of_date() -> bool:
    last_updated = get_last_update_timestamp()
    dump_timestamp = get_dump_timestamp()
    return last_updated < dump_timestamp


@contextlib.contextmanager
def download_dump() -> str:
    with tempfile.NamedTemporaryFile(suffix=".dmp.bz2") as download_file:
        with httpx.stream("GET", os.getenv("DB_DUMP_URL"), headers={"Accept-Encoding": "identity"}) as response:
            total = int(response.headers["Content-Length"])

            with tqdm(total=total, unit_scale=True, unit_divisor=1024, unit="B") as progress:
                num_bytes_downloaded = response.num_bytes_downloaded
                for chunk in response.iter_bytes():
                    download_file.write(chunk)
                    progress.update(response.num_bytes_downloaded - num_bytes_downloaded)
                    num_bytes_downloaded = response.num_bytes_downloaded

            yield download_file.name


@contextlib.contextmanager
def decompressed(bz2_file_path: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".dmp") as file, BZ2File(bz2_file_path, "r") as bz2_file:
        for data in iter(lambda: bz2_file.read(100 * 1024), b""):
            file.write(data)

        yield file.name


def restore_dump(dump_file: str) -> None:
    with decompressed(dump_file) as dump:
        docker_executable = os.getenv("DOCKER_EXECUTABLE")
        sde_container_name = os.getenv("SDE_CONTAINER_NAME")
        sde_db_username = os.getenv("SDE_DB_USERNAME")
        sde_db_name = os.getenv("SDE_DB_NAME")

        restore_cmd = f"pg_restore -c -C -U {sde_db_username} -v -d {sde_db_name} < {dump}"

        if docker_executable:
            restore_cmd = f"{docker_executable} exec -i {sde_container_name} " + restore_cmd

        subprocess.run(restore_cmd, shell=True)
        set_update_timestamp()

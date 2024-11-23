import os
import contextlib
import sys
import tempfile
import subprocess
from bz2 import BZ2File
from typing import Optional

from dateutil import parser
from datetime import datetime, timezone
import requests
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


def get_dump_timestamp(dump_url: Optional[str] = None) -> datetime:
    if not dump_url:
        dump_url = os.getenv("DB_DUMP_URL")
    res = requests.head(dump_url)
    last_modified_header = res.headers.get("Last-Modified")
    if not last_modified_header:
        raise Exception("Last-Modified header missing.")
    return parser.parse(last_modified_header)


def is_out_of_date() -> bool:
    last_updated = get_last_update_timestamp()
    dump_timestamp = get_dump_timestamp()
    return last_updated < dump_timestamp


def get_dump_checksum(dump_url: str) -> Optional[str]:
    checksum_url = f"{dump_url}.md5"
    res = requests.get(checksum_url)
    if res.status_code == 200:
        return res.text.split()[0] if res.text else None


@contextlib.contextmanager
def download_dump() -> str:
    with tempfile.NamedTemporaryFile(suffix=".dmp.bz2") as download_file:
        with requests.get(os.getenv("DB_DUMP_URL"), stream=True) as response:
            with tqdm(unit_scale=True, unit_divisor=1024, unit="B") as progress:
                num_bytes_downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    download_file.write(chunk)
                    progress.update(len(chunk) - num_bytes_downloaded)
                    num_bytes_downloaded = len(chunk)

            yield download_file.name


@contextlib.contextmanager
def decompressed(bz2_file_path: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".dmp") as file, BZ2File(bz2_file_path, "r") as bz2_file:
        for data in iter(lambda: bz2_file.read(100 * 1024), b""):
            file.write(data)

        yield file.name


def _prepare_database(docker_executable: str, sde_container_name: str, sde_db_username: str, sde_db_name: str):
    # Recreates the database with template0 to avoid any conflicts
    # https://www.postgresql.org/docs/9.2/app-pgrestore.html#APP-PGRESTORE-EXAMPLES
    drop_command = f"dropdb -U {sde_db_username} --if-exists {sde_db_name}"
    create_command = f"createdb -U {sde_db_username} -T template0 {sde_db_name}"
    if docker_executable:
        drop_command = f"{docker_executable} exec -i {sde_container_name} " + drop_command
        create_command = f"{docker_executable} exec -i {sde_container_name} " + create_command

    subprocess.run(drop_command, shell=True)
    subprocess.run(create_command, shell=True)


def restore_dump(dump_file: str) -> None:
    with decompressed(dump_file) as dump:
        docker_executable = os.getenv("DOCKER_EXECUTABLE")
        sde_container_name = os.getenv("SDE_CONTAINER_NAME")
        sde_db_username = os.getenv("SDE_DB_USERNAME")
        sde_db_name = os.getenv("SDE_DB_NAME")

        restore_cmd = f"pg_restore --no-owner -U {sde_db_username} -v -d {sde_db_name} < {dump}"
        if docker_executable:
            restore_cmd = f"{docker_executable} exec -i {sde_container_name} " + restore_cmd

        try:
            _prepare_database(docker_executable, sde_container_name, sde_db_username, sde_db_name)
            subprocess.run(restore_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            set_update_timestamp()
            print("Database dump restored succesfully!")
        except subprocess.CalledProcessError as e:
            print("--- FAILED TO RESTORE DUMP ---", file=sys.stderr)
            print(f"Error output:\n{e.stdout.decode('utf-8')}\n{e.stderr.decode('utf-8')}", file=sys.stderr)
            exit(e.returncode)

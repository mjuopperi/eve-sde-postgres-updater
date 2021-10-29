import argparse
import os
import sys
from typing import Tuple

import httpx
from httpx import Response

from config import config
from sde_updater import is_out_of_date, set_update_timestamp, get_dump_timestamp, get_dump_checksum

GITHUB_API = "https://api.github.com"


def setup_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EVE SDE Poller")
    parser.add_argument("-e", "--env", metavar="<env file name>", type=str, default=".env", help="Env file to use")
    parser.add_argument("-t", "--token", metavar="<auth token>", type=str, help="Github auth token")
    parser.add_argument("-b", "--branch", metavar="<git brahcn>", type=str, help="Git branch", default="master")

    return parser.parse_args()


def github_request(url: str, data: dict, token: str) -> Response:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    return httpx.post(url, json=data, headers=headers)


def get_tags(dump_url: str) -> Tuple[str, str]:
    dump_date = get_dump_timestamp(dump_url)
    date_tag = dump_date.strftime("%Y-%m-%d_%H-%M")
    checksum_tag = get_dump_checksum(dump_url)
    return date_tag, checksum_tag


def start_workflow(git_branch: str, github_token: str) -> bool:
    workflow_file = "build-images.yml"
    url = f"{GITHUB_API}/repos/mjuopperi/eve-sde-postgres-updater/actions/workflows/{workflow_file}/dispatches"

    date_tag, checksum_tag = get_tags(os.getenv("DB_DUMP_URL"))
    data = {
        "ref": git_branch,
        "inputs": {
            "date-tag": date_tag,
            "checksum-tag": checksum_tag,
        },
    }
    res = github_request(url=url, data=data, token=github_token)
    if res.status_code == 204:
        return True

    print(f"{res.status_code} status from GitHub API: {res.text}", file=sys.stderr)
    return False


def main():
    args = setup_cli()
    config.setup(env_file_name=args.env)

    if is_out_of_date():
        print("Database out of date. Starting GHA workflow.")
        if start_workflow(args.branch, args.token):
            set_update_timestamp()
            print("Workflow started.")
        else:
            print("Failed to start workflow.", file=sys.stderr)
            exit(1)
    else:
        print("Already up to date.")


if __name__ == "__main__":
    main()

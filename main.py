import argparse
from config import config
from sde_updater import is_out_of_date, download_dump, restore_dump


def setup_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EVE SDE Postgres updater")
    parser.add_argument("-e", "--env", metavar="<env file name>", type=str, default=".env", help="Env file to use")

    return parser.parse_args()


def main():
    args = setup_cli()
    config.setup(env_file_name=args.env)

    if is_out_of_date():
        print("Database out of date. Downloading dump...")
        with download_dump() as dump_file:
            print("Restoring dump...")
            restore_dump(dump_file)

    else:
        print("Already up to date")


if __name__ == "__main__":
    main()

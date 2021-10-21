from pathlib import Path

from dotenv import load_dotenv


def setup(env_file_name: str = ".env"):
    env_path = Path(".") / "config" / env_file_name
    load_dotenv(dotenv_path=env_path)

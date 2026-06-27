from importlib.metadata import PackageNotFoundError, version
import os
import sys

APP_DISTRIBUTION_NAME = "5050-sc-monitor"
APP_EXE_NAME = "5050 SC 监听器"


def get_app_version():
    try:
        return version(APP_DISTRIBUTION_NAME)
    except PackageNotFoundError:
        print(
            f"Package metadata for {APP_DISTRIBUTION_NAME!r} was not found.\n"
            "Run this first:\n"
            "  uv --no-cache pip install -e . --no-build-isolation --no-deps",
            file=sys.stderr,
        )
        raise SystemExit(1)


def main():
    from PyInstaller.__main__ import run

    app_version = get_app_version()
    app_name = f"{APP_EXE_NAME} [{app_version}]"
    run([
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        app_name,
        "--icon",
        "resources/favicon.ico",
        "--copy-metadata",
        APP_DISTRIBUTION_NAME,
        "--add-data",
        f"resources/favicon.ico{os.pathsep}resources",
        "main.py",
    ])


if __name__ == "__main__":
    main()

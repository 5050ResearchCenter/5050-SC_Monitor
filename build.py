import os
from pathlib import Path
import tomllib

APP_EXE_NAME = "5050 SC 监听器"
PROJECT_FILE = Path(__file__).with_name("pyproject.toml")
VERSION_ENV_VAR = "SC_MONITOR_VERSION"
VERSION_HOOK_FILE = Path(__file__).with_name("_pyinstaller_version_hook.py")


def get_app_version():
    with PROJECT_FILE.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def write_version_hook(version):
    VERSION_HOOK_FILE.write_text(
        f'import os\nos.environ[{VERSION_ENV_VAR!r}] = {version!r}\n',
        encoding="utf-8",
    )


def main():
    from PyInstaller.__main__ import run

    app_version = get_app_version()
    write_version_hook(app_version)
    app_name = f"{APP_EXE_NAME} [{app_version}]"
    run([
        "--clean",
        "--onefile",
        "--noupx",
        "--windowed",
        "--name",
        app_name,
        "--icon",
        "resources/favicon.ico",
        "--runtime-hook",
        str(VERSION_HOOK_FILE),
        "--add-data",
        f"resources/favicon.ico{os.pathsep}resources",
        "main.py",
    ])


if __name__ == "__main__":
    main()

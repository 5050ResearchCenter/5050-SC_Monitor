import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import sys
import tempfile
import tomllib
import zipfile

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


def extract_zip_library(archive_path, archive_root, destination):
    """Extract one library directory from Python's Tcl/Tk 9 zip archives."""
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts
            if not parts or parts[0] != archive_root or len(parts) == 1:
                continue
            target = destination.joinpath(*parts[1:])
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def prepare_tcl_tk_data(output_directory, tcl_root=None):
    """Prepare Tcl/Tk 9 data folders expected by PyInstaller's runtime hook."""
    tcl_root = Path(tcl_root or Path(sys.base_prefix) / "tcl")
    tcl_archives = sorted(tcl_root.glob("libtcl*.zip"))
    tk_archives = sorted(tcl_root.glob("libtk*.zip"))
    if not tcl_archives and not tk_archives:
        return []
    if not tcl_archives or not tk_archives:
        raise RuntimeError(f"Tcl/Tk 资源不完整: {tcl_root}")

    output_directory = Path(output_directory)
    tcl_destination = output_directory / "_tcl_data"
    tk_destination = output_directory / "_tk_data"
    extract_zip_library(tcl_archives[-1], "tcl_library", tcl_destination)
    extract_zip_library(tk_archives[-1], "tk_library", tk_destination)
    if not (tcl_destination / "init.tcl").is_file():
        raise RuntimeError("Tcl 资源中缺少 init.tcl")
    if not (tk_destination / "tk.tcl").is_file():
        raise RuntimeError("Tk 资源中缺少 tk.tcl")
    return [
        (tcl_destination, "_tcl_data"),
        (tk_destination, "_tk_data"),
    ]


def main():
    from PyInstaller.__main__ import run

    app_version = get_app_version()
    write_version_hook(app_version)
    app_name = f"{APP_EXE_NAME} [{app_version}]"
    with tempfile.TemporaryDirectory(prefix="sc-monitor-tk-") as temp_directory:
        tcl_tk_data = prepare_tcl_tk_data(temp_directory)
        args = [
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
        ]
        for source, destination in tcl_tk_data:
            args.extend(("--add-data", f"{source}{os.pathsep}{destination}"))
        args.append("main.py")
        run(args)


if __name__ == "__main__":
    main()

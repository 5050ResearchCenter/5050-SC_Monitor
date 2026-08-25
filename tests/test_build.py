from pathlib import Path
import tempfile
import unittest
import zipfile

from build import extract_zip_library, prepare_tcl_tk_data


class TclTkBuildTests(unittest.TestCase):
    def test_extract_zip_library_removes_archive_root_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "libtcl9.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("tcl_library/init.tcl", "package provide Tcl 9.0")
                archive.writestr("other/ignored.txt", "ignored")

            destination = root / "output"
            extract_zip_library(archive_path, "tcl_library", destination)

            self.assertTrue((destination / "init.tcl").is_file())
            self.assertFalse((destination / "tcl_library").exists())
            self.assertFalse((destination / "ignored.txt").exists())

    def test_prepare_tcl_tk_data_creates_pyinstaller_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tcl_root = root / "tcl"
            tcl_root.mkdir()
            with zipfile.ZipFile(tcl_root / "libtcl9.zip", "w") as archive:
                archive.writestr("tcl_library/init.tcl", "tcl init")
            with zipfile.ZipFile(tcl_root / "libtk9.zip", "w") as archive:
                archive.writestr("tk_library/tk.tcl", "tk init")

            data_files = prepare_tcl_tk_data(root / "prepared", tcl_root)

            self.assertEqual(
                [(destination.name, target) for destination, target in data_files],
                [("_tcl_data", "_tcl_data"), ("_tk_data", "_tk_data")],
            )
            self.assertTrue((root / "prepared" / "_tcl_data" / "init.tcl").is_file())
            self.assertTrue((root / "prepared" / "_tk_data" / "tk.tcl").is_file())


if __name__ == "__main__":
    unittest.main()

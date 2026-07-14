"""Tests for fileio.py's desktop (plain-path) branch -- the Android/SAF branch
needs pyjnius/android, which only exist in a packaged APK, so it's untestable
outside a real device (see android/README.md)."""
import fileio

assert not fileio.IS_ANDROID, "these tests only exercise fileio's desktop branch"


def test_list_dir_bin_files_missing_folder_returns_empty():
    assert fileio.list_dir_bin_files("/no/such/folder") == []


def test_list_dir_bin_files_empty_folder_returns_empty(tmp_path):
    assert fileio.list_dir_bin_files(str(tmp_path)) == []


def test_list_dir_bin_files_filters_and_sorts(tmp_path):
    (tmp_path / "vmu_save_C2.bin").write_bytes(b"a")
    (tmp_path / "vmu_save_C1.BIN").write_bytes(b"b")  # case-insensitive match
    (tmp_path / "notes.txt").write_bytes(b"ignore me")

    results = fileio.list_dir_bin_files(str(tmp_path))

    names = [n for n, _path in results]
    assert names == ["vmu_save_C1.BIN", "vmu_save_C2.bin"]
    # paired path must actually point at that same file
    assert dict(results)[names[0]] == str(tmp_path / "vmu_save_C1.BIN")


def test_read_write_bytes_round_trip(tmp_path):
    path = str(tmp_path / "vmu_save_C1.bin")
    fileio.write_bytes(path, b"\x01\x02\x03")
    assert fileio.read_bytes(path) == b"\x01\x02\x03"


def test_ensure_backup_creates_sibling_with_original_content(tmp_path):
    path = tmp_path / "vmu_save_C1.bin"
    path.write_bytes(b"original")

    fileio.ensure_backup(str(tmp_path), str(path), "vmu_save_C1.bin.bak")

    assert (tmp_path / "vmu_save_C1.bin.bak").read_bytes() == b"original"


def test_ensure_backup_does_not_overwrite_existing_backup(tmp_path):
    path = tmp_path / "vmu_save_C1.bin"
    path.write_bytes(b"edited")
    backup_path = tmp_path / "vmu_save_C1.bin.bak"
    backup_path.write_bytes(b"pre-edit original")

    fileio.ensure_backup(str(tmp_path), str(path), "vmu_save_C1.bin.bak")

    assert backup_path.read_bytes() == b"pre-edit original"

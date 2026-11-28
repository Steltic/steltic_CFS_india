"""The pinned India HR bytes must compare correctly through a Windows Git checkout."""
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_vendored


def test_vendored_bytes_obey_git_line_endings_and_preserve_real_differences(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(check_vendored, "CFS_ROOT", str(tmp_path))
    (tmp_path / ".gitattributes").write_text("*.py text eol=crlf\n*.bin -text\n", encoding="utf8")
    path = tmp_path / "viewer.py"
    source = b'unit = "mm"\n'
    path.write_bytes(source.replace(b"\n", b"\r\n"))
    assert check_vendored.matches_committed(path, source)
    assert not check_vendored.matches_committed(path, b'unit = "m"\n')
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"raw\r\n")
    assert not check_vendored.matches_committed(binary, b"raw\n")

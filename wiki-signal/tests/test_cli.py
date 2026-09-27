import pytest
from wiki_signal import cli


def test_version(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["--version"])
    assert info.value.code == 0
    assert "wiki-signal" in capsys.readouterr().out


def test_bad_arguments_use_error_next_shape(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["no-such-command"])
    assert info.value.code == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert err.startswith("Error: ")
    assert "\nNext: Run `wiki.py --help`" in err


def test_skill_error_is_printed_without_traceback(tmp_path, capsys):
    assert cli.main(["report", "--run", str(tmp_path)]) == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert err.startswith(f"Error: {tmp_path} is not an analyze run folder")
    assert "\nNext: Run analyze first" in err
    assert "Traceback" not in err


def test_unexpected_exception_is_logged_not_shown(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WIKI_SIGNAL_CACHE_DIR", str(tmp_path))

    def boom(args):
        raise ZeroDivisionError("bad")

    monkeypatch.setattr(cli, "_report", boom)
    assert cli.main(["report", "--run", str(tmp_path)]) == cli.EXIT_INTERNAL
    err = capsys.readouterr().err
    assert "internal error in wiki-signal (ZeroDivisionError: bad)" in err
    assert "Do not write your own code" in err
    assert "Traceback" not in err
    assert "ZeroDivisionError" in (tmp_path / "logs" / "last-error.txt").read_text()

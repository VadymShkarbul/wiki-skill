import pytest
from wiki_interest import cli


def test_version(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["--version"])
    assert info.value.code == 0
    assert "wiki-interest" in capsys.readouterr().out


def test_bad_arguments_use_error_next_shape(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["no-such-command"])
    assert info.value.code == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert err.startswith("Error: ")
    assert "\nNext: Run `wiki.py --help`" in err


def test_skill_error_is_printed_without_traceback(capsys):
    assert cli.main(["resolve"]) == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert err.startswith("Error: `resolve` is not implemented")
    assert "Traceback" not in err


def test_unexpected_exception_is_logged_not_shown(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WIKI_INTEREST_CACHE_DIR", str(tmp_path))

    def boom(args):
        raise ZeroDivisionError("bad")

    monkeypatch.setattr(cli, "_not_implemented", boom)
    assert cli.main(["resolve"]) == cli.EXIT_INTERNAL
    err = capsys.readouterr().err
    assert "internal error in wiki-interest (ZeroDivisionError: bad)" in err
    assert "Do not write your own code" in err
    assert "Traceback" not in err
    assert "ZeroDivisionError" in (tmp_path / "logs" / "last-error.txt").read_text()

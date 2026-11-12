from __future__ import annotations

from unittest.mock import patch

import pytest

from gbif_mcp import __version__
from gbif_mcp.server import main, parse_args


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "gbif-mcp" in captured.out
    assert "--transport" in captured.out


def test_cli_defaults() -> None:
    args = parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_cli_main_stdio() -> None:
    with patch("mcp.server.MCPServer.run") as mock_run:
        ret = main(["--transport", "stdio"])
        assert ret == 0
        mock_run.assert_called_once_with(transport="stdio")


def test_cli_main_sse() -> None:
    with patch("mcp.server.MCPServer.run") as mock_run:
        ret = main(["--transport", "sse", "--host", "0.0.0.0", "--port", "9000"])
        assert ret == 0
        mock_run.assert_called_once_with(transport="sse", host="0.0.0.0", port=9000)


def test_main_module_execution() -> None:
    import runpy

    with patch("gbif_mcp.server.main", return_value=0):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("gbif_mcp.__main__", run_name="__main__")
        assert exc.value.code == 0

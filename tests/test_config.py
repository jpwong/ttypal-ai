import os
import tempfile
from pathlib import Path

import pytest

from ttypal.config import (
    load_board, save_board, list_boards, delete_board, DEFAULT_CONFIG,
)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("ttypal.config.CONFIG_DIR", tmp_path)
    return tmp_path


def test_save_and_load(config_dir):
    cfg = {"serial": {"port": "/dev/ttyUSB0", "baudrate": 115200},
           "log": {}, "socket": {}}
    save_board("test1", cfg)
    loaded = load_board("test1")
    assert loaded["serial"]["port"] == "/dev/ttyUSB0"
    assert loaded["serial"]["baudrate"] == 115200


def test_list_boards(config_dir):
    save_board("alpha", DEFAULT_CONFIG)
    save_board("beta", DEFAULT_CONFIG)
    boards = list_boards()
    assert boards == ["alpha", "beta"]


def test_delete_board(config_dir):
    save_board("todelete", DEFAULT_CONFIG)
    assert "todelete" in list_boards()
    delete_board("todelete")
    assert "todelete" not in list_boards()


def test_load_nonexistent(config_dir):
    assert load_board("nope") is None

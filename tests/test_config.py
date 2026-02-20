"""Tests for config module."""
import os

import pytest


def test_config_has_required_attrs():
    import config
    assert hasattr(config, "DATA_DIR")
    assert hasattr(config, "ARCHIVE_DIR")
    assert hasattr(config, "DB_PATH")


def test_config_paths_are_strings():
    import config
    assert isinstance(config.DATA_DIR, str)
    assert isinstance(config.ARCHIVE_DIR, str)
    assert isinstance(config.DB_PATH, str)


def test_config_dirs_exist():
    """config ensures directories exist on import."""
    import config
    assert os.path.isdir(config.DATA_DIR)
    assert os.path.isdir(config.ARCHIVE_DIR)

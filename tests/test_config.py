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
    """config sets DATA_DIR and ARCHIVE_DIR; they exist when path is available (e.g. local or CI)."""
    import config
    if not os.path.isdir(config.DATA_DIR):
        pytest.skip("DATA_DIR not available (e.g. optional drive not mounted)")
    if not os.path.isdir(config.ARCHIVE_DIR):
        pytest.skip("ARCHIVE_DIR not available")


def test_config_etf_attrs():
    """ETF storage and archive paths exist after import."""
    import config
    assert hasattr(config, "ETF_STORAGE_ROOT")
    assert hasattr(config, "ETF_CACHE_DB")
    assert hasattr(config, "ETF_SESSIONS_DIR")
    assert hasattr(config, "ETF_ARCHIVE_DIR")
    assert isinstance(config.ETF_STORAGE_ROOT, str)
    assert os.path.isdir(os.path.dirname(config.ETF_CACHE_DB))
    assert os.path.isdir(config.ETF_SESSIONS_DIR)
    assert os.path.isdir(config.ETF_ARCHIVE_DIR)



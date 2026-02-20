"""Tests for simple_agent.tools."""
import sys
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "simple_agent"))
from simple_agent.tools import calculate, get_time, TOOL_REGISTRY, TOOL_DEFINITIONS


def test_calculate_simple():
    assert calculate("2 + 2") == "4"


def test_calculate_complex():
    assert calculate("2 + 2 * 5") == "12"


def test_calculate_error():
    result = calculate("invalid !!")
    assert "Error" in result


def test_get_time_default():
    result = get_time()
    assert "Error" not in result or "202" in result


def test_get_time_invalid_tz():
    result = get_time("Invalid/Timezone")
    assert "Error" in result


def test_tool_registry():
    assert "calculate" in TOOL_REGISTRY
    assert "get_time" in TOOL_REGISTRY

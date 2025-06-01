import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from devserver_mcp.utils import get_tool_emoji, log_error_to_file


def test_get_tool_emoji():
    assert get_tool_emoji() == "🔧"


def test_log_error_to_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)

            error = ValueError("Test error message")
            context = "test_context"

            log_error_to_file(error, context)

            log_file = Path(temp_dir) / "mcp-errors.log"
            assert log_file.exists()

            content = log_file.read_text(encoding="utf-8")
            assert "ERROR in context: test_context" in content
            assert "Error Type: ValueError" in content
            assert "Error Message: Test error message" in content
            assert f"python_version: {sys.version}" in content
            assert f"platform: {sys.platform}" in content
            assert "Full Traceback:" in content

        finally:
            os.chdir(original_cwd)


def test_log_error_to_file_no_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)

            error = RuntimeError("Another test error")

            log_error_to_file(error)

            log_file = Path(temp_dir) / "mcp-errors.log"
            assert log_file.exists()

            content = log_file.read_text(encoding="utf-8")
            assert "ERROR in context: " in content
            assert "Error Type: RuntimeError" in content
            assert "Error Message: Another test error" in content

        finally:
            os.chdir(original_cwd)


def test_log_error_to_file_handles_write_failure():
    with patch("devserver_mcp.utils.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/nonexistent/impossible/path")
        error = Exception("Test error")

        log_error_to_file(error, "test")


def test_log_error_to_file_appends_to_existing_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)

            log_file = Path(temp_dir) / "mcp-errors.log"
            log_file.write_text("Existing content\n", encoding="utf-8")

            error = ValueError("Test error")
            log_error_to_file(error, "test")

            content = log_file.read_text(encoding="utf-8")
            assert "Existing content" in content
            assert "Error Type: ValueError" in content

        finally:
            os.chdir(original_cwd)

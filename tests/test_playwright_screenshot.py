import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp.playwright import PlaywrightOperator


@pytest.mark.asyncio
async def test_screenshot_filename_sanitization():
    with patch("devserver_mcp.playwright.async_playwright"):
        operator = PlaywrightOperator()
        operator._page = MagicMock()
        operator._page.screenshot = AsyncMock()
        operator._page.url = "https://example.com"

        with tempfile.TemporaryDirectory() as tmpdir:
            screenshots_dir = Path(tmpdir) / "screenshots"

            with patch("devserver_mcp.playwright.Path") as mock_path:
                mock_path.return_value = screenshots_dir

                test_cases = [
                    ("normal_name", "normal_name.png"),
                    ("name with spaces", "name_with_spaces.png"),
                    ("../../etc/passwd", "etc_passwd.png"),
                    ("name/with/slashes", "name_with_slashes.png"),
                    ("name\\with\\backslashes", "name_with_backslashes.png"),
                    ("name:with:colons", "name_with_colons.png"),
                    ("name*with*asterisks", "name_with_asterisks.png"),
                    ("name?with?questions", "name_with_questions.png"),
                    ("name<with>brackets", "name_with_brackets.png"),
                    ("name|with|pipes", "name_with_pipes.png"),
                    ('name"with"quotes', "name_with_quotes.png"),
                    ("....", "screenshot.png"),
                    ("name.png", "name.png"),
                    ("name.jpg.png", "name.jpg.png"),
                ]

                for input_name, expected_filename in test_cases:
                    result = await operator.screenshot(name=input_name)

                    operator._page.screenshot.assert_called()

                    assert result["status"] == "success"
                    assert result["filename"] == expected_filename


@pytest.mark.asyncio
async def test_screenshot_duplicate_filename_handling():
    with patch("devserver_mcp.playwright.async_playwright"):
        operator = PlaywrightOperator()
        operator._page = MagicMock()
        operator._page.screenshot = AsyncMock()
        operator._page.url = "https://example.com"

        with tempfile.TemporaryDirectory() as tmpdir:
            screenshots_dir = Path(tmpdir) / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)

            (screenshots_dir / "test.png").touch()
            (screenshots_dir / "test_1.png").touch()

            with patch("devserver_mcp.playwright.Path") as mock_path:
                mock_path.return_value = screenshots_dir

                result = await operator.screenshot(name="test")

                assert result["filename"] == "test_2.png"
                assert "test_2.png" in result["path"]


@pytest.mark.asyncio
async def test_screenshot_creates_directory():
    with patch("devserver_mcp.playwright.async_playwright"):
        operator = PlaywrightOperator()
        operator._page = MagicMock()
        operator._page.screenshot = AsyncMock()
        operator._page.url = "https://example.com"

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                screenshots_dir = Path("screenshots")
                assert not screenshots_dir.exists()

                await operator.screenshot()

                assert screenshots_dir.exists()
            finally:
                os.chdir(original_cwd)

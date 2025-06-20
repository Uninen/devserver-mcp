import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from devserver_mcp.state import StateManager


def test_state_manager_creates_state_directory():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        assert manager.state_dir.exists()
        assert manager.state_dir.name == ".devserver-mcp"


def test_save_pid_creates_state_file():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        
        manager.save_pid("myservice", 12345)
        
        assert manager.state_file.exists()
        assert manager.get_pid("myservice") == 12345


def test_get_pid_returns_none_for_missing_service():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        
        assert manager.get_pid("nonexistent") is None


def test_clear_pid_removes_service():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        
        manager.save_pid("myservice", 12345)
        manager.clear_pid("myservice")
        
        assert manager.get_pid("myservice") is None


def test_clear_pid_handles_missing_service():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        
        manager.clear_pid("nonexistent")


def test_cleanup_dead_removes_dead_processes():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        
        current_pid = os.getpid()
        manager.save_pid("alive", current_pid)
        manager.save_pid("dead", 99999999)
        
        manager.cleanup_dead()
        
        assert manager.get_pid("alive") == current_pid
        assert manager.get_pid("dead") is None


def test_multiple_projects_have_separate_state_files():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager1 = StateManager("/path/to/project1")
        manager2 = StateManager("/path/to/project2")
        
        manager1.save_pid("service", 111)
        manager2.save_pid("service", 222)
        
        assert manager1.get_pid("service") == 111
        assert manager2.get_pid("service") == 222


def test_state_persists_across_manager_instances():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager1 = StateManager("/path/to/project")
        manager1.save_pid("myservice", 12345)
        
        manager2 = StateManager("/path/to/project")
        assert manager2.get_pid("myservice") == 12345


def test_handles_corrupted_state_file():
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        manager = StateManager("/path/to/project")
        
        manager.state_file.write_text("invalid json content")
        
        assert manager.get_pid("myservice") is None
        
        manager.save_pid("myservice", 12345)
        assert manager.get_pid("myservice") == 12345
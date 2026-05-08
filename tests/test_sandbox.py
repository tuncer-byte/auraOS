"""Sandbox güvenlik testleri."""
import pytest
from auraos.sandbox.workspace import Workspace, WorkspaceSecurityError
from auraos.sandbox.shell import SafeShell


def test_workspace_blocks_traversal(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceSecurityError):
        ws.read_text("../etc/passwd")


def test_workspace_blocks_absolute(tmp_path):
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceSecurityError):
        ws.read_text("/etc/passwd")


def test_workspace_read_write(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_text("a/b.txt", "merhaba")
    assert ws.read_text("a/b.txt") == "merhaba"


def test_shell_blocks_dangerous(tmp_path):
    ws = Workspace(tmp_path)
    sh = SafeShell(ws)
    with pytest.raises(WorkspaceSecurityError):
        sh.run("rm -rf /")


def test_shell_blocks_unlisted(tmp_path):
    ws = Workspace(tmp_path)
    sh = SafeShell(ws)
    with pytest.raises(WorkspaceSecurityError):
        sh.run("nmap localhost")


def test_shell_runs_safe(tmp_path):
    ws = Workspace(tmp_path)
    sh = SafeShell(ws)
    res = sh.run("echo hello")
    assert "hello" in res["stdout"]

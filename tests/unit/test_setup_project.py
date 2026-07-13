"""Unit tests for setup.py (project setup script)."""
import importlib.util
import os
import sys
import tempfile

import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SPEC = importlib.util.spec_from_file_location(
    "setup_project",
    os.path.join(_PROJECT_ROOT, "setup.py"),
)
setup_project = importlib.util.module_from_spec(_SPEC)
sys.modules["setup_project"] = setup_project
_SPEC.loader.exec_module(setup_project)

import setup_lib.constants as _setup_constants


# ---------------------------------------------------------------------------
# _parse_export_file
# ---------------------------------------------------------------------------
def test_parse_export_file_missing_returns_empty():
    assert setup_project._parse_export_file("/nonexistent/path") == {}


def test_parse_export_file_parses_export_lines():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write('export FOO=bar\n')
        f.write('export BAR="baz"\n')
        f.write("export QUX='quux'\n")
        f.write("# export SKIP=no\n")
        f.write("not export BAD=line\n")
        path = f.name
    try:
        out = setup_project._parse_export_file(path)
        assert out["FOO"] == "bar"
        assert out["BAR"] == "baz"
        assert out["QUX"] == "quux"
        assert "SKIP" not in out
        assert "BAD" not in out
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Constants consistency
# ---------------------------------------------------------------------------
def test_app_types_and_trigger_map_consistent():
    assert set(setup_project.APP_TYPES) == set(setup_project.TRIGGER_TYPE_MAP.keys())


def test_ecs_app_types():
    assert setup_project.APP_TYPES == ("api", "internal_api", "background_service", "scheduled")


# ---------------------------------------------------------------------------
# Placeholder checks
# ---------------------------------------------------------------------------
def test_is_placeholder_bucket():
    assert setup_project._is_placeholder_bucket("mycompany-terraform-state") is True
    assert setup_project._is_placeholder_bucket("") is True
    assert setup_project._is_placeholder_bucket("real-bucket") is False


def test_is_placeholder_role():
    assert setup_project._is_placeholder_role("arn:aws:iam::1234567890:role/test") is True
    assert setup_project._is_placeholder_role("") is True
    assert setup_project._is_placeholder_role("arn:aws:iam::999999999999:role/real") is False


# ---------------------------------------------------------------------------
# AWS region detection
# ---------------------------------------------------------------------------
def test_detect_probable_aws_region_from_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    assert setup_project.detect_probable_aws_region() == "eu-central-1"


def test_resolve_aws_region_prefers_cli(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    assert setup_project.resolve_aws_region("ap-southeast-2", {}) == "ap-southeast-2"


def test_resolve_aws_region_keeps_configured_project(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    current = {
        "aws_region": "us-east-1",
        "terraform_state_bucket": "real-bucket",
    }
    assert setup_project.resolve_aws_region("", current) == "us-east-1"


def test_resolve_aws_region_detects_for_fresh_template(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    current = {
        "aws_region": "us-west-2",
        "terraform_state_bucket": setup_project.TERRAFORM_STATE_BUCKET_PLACEHOLDER,
    }
    assert setup_project.resolve_aws_region("", current) == "ca-central-1"


def test_approval_mode_for_plan():
    assert setup_project.approval_mode_for_plan("enterprise") == "environment"
    assert setup_project.approval_mode_for_plan("team") == "dispatch"
    assert setup_project.approval_mode_for_plan("") == "dispatch"


def test_parse_gh_auth_accounts():
    text = """
github.com
  ✓ Logged in to github.com account alice (keyring)
  - Active account: true
  ✓ Logged in to github.com account bob (keyring)
  - Active account: false
"""
    accounts = setup_project.parse_gh_auth_accounts(text)
    assert accounts[0]["login"] == "alice"
    assert accounts[0]["active"] is True
    assert accounts[1]["login"] == "bob"
    assert accounts[1]["active"] is False


def test_find_gh_executable_respects_which(monkeypatch):
    monkeypatch.setattr(setup_project.shutil, "which", lambda _: "/usr/bin/gh")
    assert setup_project.find_gh_executable() == "/usr/bin/gh"


# ---------------------------------------------------------------------------
# CLI --help
# ---------------------------------------------------------------------------
def test_main_help_exits_zero():
    orig = sys.argv
    try:
        sys.argv = ["setup.py", "--help"]
        with pytest.raises(SystemExit) as exc_info:
            setup_project.main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = orig


# ---------------------------------------------------------------------------
# --non-interactive without required args
# ---------------------------------------------------------------------------
def test_main_non_interactive_missing_required(capsys, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    orig = sys.argv
    try:
        sys.argv = ["setup.py", "--non-interactive"]
        result = setup_project.main()
        assert result == 1
        err = capsys.readouterr().err.lower()
        assert "required" in err or "app" in err
    finally:
        sys.argv = orig


# ---------------------------------------------------------------------------
# Full non-interactive run writes config files
# ---------------------------------------------------------------------------
def test_non_interactive_full_run_writes_configs(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")

    # Create minimal go.mod
    cmd_dir = tmp_path / "cmd" / "app"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "main.go").write_text("package main\nfunc main() {}\n")
    (tmp_path / "go.mod").write_text("module old-name\ngo 1.26\n")

    # Patch paths
    monkeypatch.setattr(_setup_constants, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(_setup_constants, "CONFIG_GLOBAL", str(tmp_path / "config.global"))
    monkeypatch.setattr(_setup_constants, "CONFIG_STAGING", str(tmp_path / "config.staging"))
    monkeypatch.setattr(_setup_constants, "CONFIG_PROD", str(tmp_path / "config.prod"))
    monkeypatch.setattr(_setup_constants, "MAIN_GO_PATH", str(cmd_dir / "main.go"))
    monkeypatch.setattr(_setup_constants, "GO_MOD_PATH", str(tmp_path / "go.mod"))

    orig = sys.argv
    try:
        sys.argv = [
            "setup.py", "--non-interactive",
            "--app-type", "api",
            "--app-name", "test-app",
            "--terraform-state-bucket", "my-bucket",
            "--aws-role-arn", "arn:aws:iam::999:role/test",
        ]
        result = setup_project.main()
        assert result == 0
    finally:
        sys.argv = orig

    # Verify config files were written
    assert (tmp_path / "config.global").exists()
    assert (tmp_path / "config.staging").exists()
    assert (tmp_path / "config.prod").exists()

    global_text = (tmp_path / "config.global").read_text()
    assert "test-app" in global_text
    assert "my-bucket" in global_text
    assert "ecs_api_service" in global_text
    assert "export PROJECT_NAME=test-app" in global_text
    assert "export MANAGE_PROJECT_RESOURCE_GROUP=true" in global_text
    assert "export AWS_REGION=" in global_text

    staging_text = (tmp_path / "config.staging").read_text()
    assert "API_ROOT_DOMAIN" in staging_text

    # Verify go.mod was updated
    go_mod = (tmp_path / "go.mod").read_text()
    assert "module test-app" in go_mod

    # Verify main.go has Fiber content (api type)
    main_go = (cmd_dir / "main.go").read_text()
    assert "fiber" in main_go.lower() or "Fiber" in main_go


def test_non_interactive_shared_project_name(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")

    cmd_dir = tmp_path / "cmd" / "app"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "main.go").write_text("package main\nfunc main() {}\n")
    (tmp_path / "go.mod").write_text("module old-name\ngo 1.26\n")

    monkeypatch.setattr(_setup_constants, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(_setup_constants, "CONFIG_GLOBAL", str(tmp_path / "config.global"))
    monkeypatch.setattr(_setup_constants, "CONFIG_STAGING", str(tmp_path / "config.staging"))
    monkeypatch.setattr(_setup_constants, "CONFIG_PROD", str(tmp_path / "config.prod"))
    monkeypatch.setattr(_setup_constants, "MAIN_GO_PATH", str(cmd_dir / "main.go"))
    monkeypatch.setattr(_setup_constants, "GO_MOD_PATH", str(tmp_path / "go.mod"))

    orig = sys.argv
    try:
        sys.argv = [
            "setup.py", "--non-interactive",
            "--app-type", "scheduled",
            "--app-name", "backend-api",
            "--project-name", "checkout",
            "--manage-project-resource-group", "false",
            "--terraform-state-bucket", "my-bucket",
            "--aws-role-arn", "arn:aws:iam::999:role/test",
        ]
        result = setup_project.main()
        assert result == 0
    finally:
        sys.argv = orig

    global_text = (tmp_path / "config.global").read_text()
    assert "export PROJECT_NAME=checkout" in global_text
    assert "export MANAGE_PROJECT_RESOURCE_GROUP=false" in global_text
    assert "backend-api" in global_text


def test_non_interactive_internal_api_type(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")

    cmd_dir = tmp_path / "cmd" / "app"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "main.go").write_text("package main\nfunc main() {}\n")
    (tmp_path / "go.mod").write_text("module old-name\ngo 1.26\n")

    monkeypatch.setattr(_setup_constants, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(_setup_constants, "CONFIG_GLOBAL", str(tmp_path / "config.global"))
    monkeypatch.setattr(_setup_constants, "CONFIG_STAGING", str(tmp_path / "config.staging"))
    monkeypatch.setattr(_setup_constants, "CONFIG_PROD", str(tmp_path / "config.prod"))
    monkeypatch.setattr(_setup_constants, "MAIN_GO_PATH", str(cmd_dir / "main.go"))
    monkeypatch.setattr(_setup_constants, "GO_MOD_PATH", str(tmp_path / "go.mod"))

    orig = sys.argv
    try:
        sys.argv = [
            "setup.py", "--non-interactive",
            "--app-type", "internal_api",
            "--app-name", "internal-app",
            "--terraform-state-bucket", "my-bucket",
            "--aws-role-arn", "arn:aws:iam::999:role/test",
        ]
        result = setup_project.main()
        assert result == 0
    finally:
        sys.argv = orig

    global_text = (tmp_path / "config.global").read_text()
    assert "export trigger_type=ecs_internal_api_service" in global_text

    staging_text = (tmp_path / "config.staging").read_text()
    assert "API_ROOT_DOMAIN" in staging_text

    # Internal API uses the same HTTP app template as the public API
    main_go = (cmd_dir / "main.go").read_text()
    assert "fiber" in main_go.lower()


def test_non_interactive_scheduled_type(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")

    cmd_dir = tmp_path / "cmd" / "app"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "main.go").write_text("package main\nfunc main() {}\n")
    (tmp_path / "go.mod").write_text("module old-name\ngo 1.26\n")

    monkeypatch.setattr(_setup_constants, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(_setup_constants, "CONFIG_GLOBAL", str(tmp_path / "config.global"))
    monkeypatch.setattr(_setup_constants, "CONFIG_STAGING", str(tmp_path / "config.staging"))
    monkeypatch.setattr(_setup_constants, "CONFIG_PROD", str(tmp_path / "config.prod"))
    monkeypatch.setattr(_setup_constants, "MAIN_GO_PATH", str(cmd_dir / "main.go"))
    monkeypatch.setattr(_setup_constants, "GO_MOD_PATH", str(tmp_path / "go.mod"))

    orig = sys.argv
    try:
        sys.argv = [
            "setup.py", "--non-interactive",
            "--app-type", "scheduled",
            "--app-name", "cron-job",
            "--terraform-state-bucket", "my-bucket",
            "--aws-role-arn", "arn:aws:iam::999:role/test",
        ]
        result = setup_project.main()
        assert result == 0
    finally:
        sys.argv = orig

    global_text = (tmp_path / "config.global").read_text()
    assert "ecs_eventbridge" in global_text

    main_go = (cmd_dir / "main.go").read_text()
    assert "Hello, World!" in main_go

#!/usr/bin/env python3
"""
Setup for AWS ECS (Go) template.
Configures app type (api | internal_api | background_service | scheduled),
config.global / config.staging / config.prod, and Go source files.
Auto-discovers OIDC role, Terraform state bucket, and Route53 domains.

Run from project root:  python3 setup.py [--app-type ...] [options]
Works on macOS and Windows (Python 3.6+). Safe to re-run.
"""

from __future__ import print_function

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import shutil  # noqa: F401 — kept so tests can monkeypatch setup_project.shutil

from setup_lib.aws_creds import (  # noqa: F401
    detect_probable_aws_region,
    resolve_aws_region,
)
from setup_lib.cli import main  # noqa: F401
from setup_lib.config_io import _parse_export_file  # noqa: F401
from setup_lib.constants import (  # noqa: F401
    APP_TYPES,
    TERRAFORM_STATE_BUCKET_PLACEHOLDER,
    TRIGGER_TYPE_MAP,
    TRIGGER_TYPE_REVERSE,
    SCRIPT_DIR,
    CONFIG_GLOBAL,
    CONFIG_STAGING,
    CONFIG_PROD,
    MAIN_GO_PATH,
    GO_MOD_PATH,
)
from setup_lib.github_gating import (  # noqa: F401
    approval_mode_for_plan,
    find_gh_executable as _find_gh_impl,
    parse_gh_auth_accounts,
)
from setup_lib.prompts import (  # noqa: F401
    _is_placeholder_bucket,
    _is_placeholder_role,
)
from setup_lib import github_gating  # noqa: F401



def find_gh_executable():
    """Locate gh; honor monkeypatch of this module's shutil.which in unit tests."""
    orig_which = github_gating.shutil.which
    github_gating.shutil.which = shutil.which
    try:
        return _find_gh_impl()
    finally:
        github_gating.shutil.which = orig_which


if __name__ == "__main__":
    sys.exit(main())

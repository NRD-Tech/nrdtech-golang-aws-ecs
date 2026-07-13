"""Constants and paths for project setup."""
from __future__ import print_function

import os

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(_PACKAGE_DIR)

CONFIG_GLOBAL = os.path.join(SCRIPT_DIR, "config.global")


CONFIG_STAGING = os.path.join(SCRIPT_DIR, "config.staging")


CONFIG_PROD = os.path.join(SCRIPT_DIR, "config.prod")


GITHUB_WORKFLOWS = os.path.join(SCRIPT_DIR, ".github", "workflows")


WORKFLOW_DISABLED = os.path.join(GITHUB_WORKFLOWS, "github_flow.yml.disabled")


WORKFLOW_ENABLED = os.path.join(GITHUB_WORKFLOWS, "github_flow.yml")


MAIN_GO_PATH = os.path.join(SCRIPT_DIR, "cmd", "app", "main.go")


GO_MOD_PATH = os.path.join(SCRIPT_DIR, "go.mod")


APPROVAL_MODES = ("dispatch", "environment")


DEFAULT_APPROVAL_MODE = "dispatch"


APP_TYPES = ("api", "internal_api", "background_service", "scheduled")


TRIGGER_TYPE_MAP = {
    "api": "ecs_api_service",
    "internal_api": "ecs_internal_api_service",
    "background_service": "ecs_background_service",
    "scheduled": "ecs_eventbridge",
}


TRIGGER_TYPE_REVERSE = {v: k for k, v in TRIGGER_TYPE_MAP.items()}



OIDC_FEDERATION = "token.actions.githubusercontent.com"


TERRAFORM_STATE_BUCKET_PLACEHOLDER = "mycompany-terraform-state"


AWS_ROLE_ARN_PLACEHOLDER_ACCOUNT = "1234567890"

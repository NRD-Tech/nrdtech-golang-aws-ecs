#!/usr/bin/env python3
"""
Setup for AWS ECS template. Configures app type (ecs_api_service | ecs_background_service | ecs_eventbridge),
config.global / config.staging / config.prod. Auto-discovers OIDC role, Terraform state bucket, and Route53 domains.
Run from project root: python3 setup.py [--app-type ...] [options]
Works on macOS and Windows (Python 3.6+). Safe to re-run; existing config values used as defaults.
"""

from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_GLOBAL = os.path.join(SCRIPT_DIR, "config.global")
CONFIG_STAGING = os.path.join(SCRIPT_DIR, "config.staging")
CONFIG_PROD = os.path.join(SCRIPT_DIR, "config.prod")
MAIN_GO_PATH = os.path.join(SCRIPT_DIR, "cmd", "app", "main.go")
GO_MOD_PATH = os.path.join(SCRIPT_DIR, "go.mod")

APP_TYPES = ("ecs_api_service", "ecs_background_service", "ecs_eventbridge")
OIDC_FEDERATION = "token.actions.githubusercontent.com"

# Template placeholders in config.global; treat as unset so discovery/prompt run
TERRAFORM_STATE_BUCKET_PLACEHOLDER = "mycompany-terraform-state"
AWS_ROLE_ARN_PLACEHOLDER_ACCOUNT = "1234567890"

# main.go bodies: Fiber (ecs_api_service) and EventBridge/scheduled. Fiber includes /healthcheck for ALB.
MAIN_GO_FIBER = '''package main

/*********************************
# Fiber API Service
*********************************/
import (
	"github.com/gofiber/fiber/v2"
	"log"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	app := fiber.New()

	app.Get("/", func(c *fiber.Ctx) error {
		return c.SendString("Hello, Fiber!")
	})
	app.Get("/ping", func(c *fiber.Ctx) error {
		return c.SendString("pong")
	})
	app.Get("/healthcheck", func(c *fiber.Ctx) error {
		return c.SendStatus(fiber.StatusOK)
	})

	go func() {
		if err := app.Listen(":8080"); err != nil {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	log.Println("Shutting down server...")
	if err := app.Shutdown(); err != nil {
		log.Fatalf("Failed to gracefully shutdown: %v", err)
	}
	log.Println("Server stopped.")
}

/*********************************
# Event Bridge Schedule
*********************************/
//import "fmt"
//
//func main() {
//	fmt.Println("Hello, World!")
//}
'''

MAIN_GO_EVENTBRIDGE = '''package main

/*********************************
# Event Bridge Schedule
*********************************/
import "fmt"

func main() {
	fmt.Println("Hello, World!")
}

/*********************************
# Fiber API Service
**********************************/
//import (
//	"github.com/gofiber/fiber/v2"
//	"log"
//	"os"
//	"os/signal"
//	"syscall"
//)
//
//func main() {
//	app := fiber.New()
//	app.Get("/", func(c *fiber.Ctx) error {
//		return c.SendString("Hello, Fiber!")
//	})
//	app.Get("/ping", func(c *fiber.Ctx) error {
//		return c.SendString("pong")
//	})
//	app.Get("/healthcheck", func(c *fiber.Ctx) error {
//		return c.SendStatus(fiber.StatusOK)
//	})
//	go func() {
//		if err := app.Listen(":8080"); err != nil {
//			log.Fatalf("Failed to start server: %v", err)
//		}
//	}()
//	c := make(chan os.Signal, 1)
//	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
//	<-c
//	log.Println("Shutting down server...")
//	if err := app.Shutdown(); err != nil {
//		log.Fatalf("Failed to gracefully shutdown: %v", err)
//	}
//	log.Println("Server stopped.")
//}
'''


def _parse_export_file(path: str) -> dict:
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("export ") or "=" not in line:
                continue
            rest = line[7:].strip()
            key, _, val = rest.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                out[key] = val
    return out


def _has_credentials() -> bool:
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        return True
    if os.environ.get("AWS_PROFILE"):
        return True
    creds_path = os.path.expanduser(os.path.join("~", ".aws", "credentials"))
    if os.path.isfile(creds_path):
        with open(creds_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == "[default]":
                    return True
    return False


def prompt_for_aws_credentials() -> None:
    """Ask user for AWS auth first: profile (default) or access key/secret; set env accordingly."""
    choice = input("Use (1) AWS profile or (2) access key/secret? [1]: ").strip() or "1"
    if choice == "2":
        key = input("AWS_ACCESS_KEY_ID: ").strip()
        secret = input("AWS_SECRET_ACCESS_KEY: ").strip()
        if key:
            os.environ["AWS_ACCESS_KEY_ID"] = key
        if secret:
            os.environ["AWS_SECRET_ACCESS_KEY"] = secret
        os.environ.pop("AWS_PROFILE", None)
    else:
        profile = input("AWS profile name: ").strip()
        if profile:
            os.environ["AWS_PROFILE"] = profile
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)


def ensure_aws_credentials() -> None:
    if _has_credentials():
        return
    print("No AWS credentials found (AWS_ACCESS_KEY_ID/SECRET, AWS_PROFILE, or ~/.aws/credentials).", file=sys.stderr)
    print("Run without --non-interactive to be prompted for profile or keys.", file=sys.stderr)
    sys.exit(1)


def _try_boto3_discover(region: str) -> dict:
    out = {"oidc_roles": [], "terraform_buckets": [], "route53_domains": []}
    try:
        import boto3
    except ImportError:
        return out
    try:
        session = boto3.Session(region_name=region)
        iam = session.client("iam")
        paginator = iam.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page.get("Roles", []):
                name = role.get("RoleName")
                arn = role.get("Arn", "")
                try:
                    r = iam.get_role(RoleName=name)
                    policy = r.get("Role", {}).get("AssumeRolePolicyDocument", {})
                    stmts = policy.get("Statement", [])
                    for s in stmts:
                        principal = s.get("Principal", {}) or {}
                        fed = principal.get("Federated") or ""
                        if isinstance(fed, list):
                            fed = " ".join(fed)
                        if OIDC_FEDERATION in str(fed):
                            out["oidc_roles"].append({"arn": arn, "name": name})
                            break
                except Exception:
                    pass
    except Exception:
        pass
    try:
        s3 = session.client("s3")
        for b in s3.list_buckets().get("Buckets", []):
            name = b.get("Name", "")
            if "terraform" in name.lower():
                out["terraform_buckets"].append(name)
    except Exception:
        pass
    try:
        r53 = session.client("route53")
        for zone in r53.list_hosted_zones().get("HostedZones", []):
            name = zone.get("Name", "").rstrip(".")
            if name:
                out["route53_domains"].append(name)
    except Exception:
        pass
    return out


def _run_aws_cli(cmd: list) -> dict:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "AWS_DEFAULT_OUTPUT": "json"},
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return {}


def _try_cli_discover(region: str) -> dict:
    out = {"oidc_roles": [], "terraform_buckets": [], "route53_domains": []}
    env = {**os.environ, "AWS_DEFAULT_REGION": region}
    paginator = _run_aws_cli(["aws", "iam", "list-roles", "--max-items", "100"])
    for role in paginator.get("Roles", []):
        arn = role.get("Arn", "")
        name = role.get("RoleName", "")
        role_detail = _run_aws_cli(["aws", "iam", "get-role", "--role-name", name]) if name else {}
        policy = (role_detail.get("Role") or {}).get("AssumeRolePolicyDocument") or {}
        for s in policy.get("Statement", []):
            principal = s.get("Principal") or {}
            fed = principal.get("Federated") or ""
            if OIDC_FEDERATION in str(fed):
                out["oidc_roles"].append({"arn": arn, "name": name})
                break
    buckets = _run_aws_cli(["aws", "s3api", "list-buckets"])
    for b in buckets.get("Buckets", []):
        name = b.get("Name", "")
        if name and "terraform" in name.lower():
            out["terraform_buckets"].append(name)
    zones = _run_aws_cli(["aws", "route53", "list-hosted-zones"])
    for z in zones.get("HostedZones", []):
        name = (z.get("Name") or "").rstrip(".")
        if name:
            out["route53_domains"].append(name)
    return out


def discover_aws_resources(region: str) -> dict:
    discovered = _try_boto3_discover(region)
    if not discovered["oidc_roles"] and not discovered["terraform_buckets"]:
        discovered = _try_cli_discover(region)
    return discovered


def _choose_from_list(prompt_msg: str, items: list, allow_custom: bool = True) -> str:
    if not items:
        return input("{}: ".format(prompt_msg)).strip()
    print(prompt_msg)
    for i, x in enumerate(items, 1):
        if isinstance(x, dict):
            label = x.get("arn") or x.get("name") or str(x)
        else:
            label = str(x)
        print("  {}: {}".format(i, label))
    if allow_custom:
        print("  0: Enter value manually")
    choice = input("Choice [1]: ").strip() or "1"
    try:
        idx = int(choice)
        if idx == 0 and allow_custom:
            return input("Value: ").strip()
        if 1 <= idx <= len(items):
            x = items[idx - 1]
            return x.get("arn") if isinstance(x, dict) and "arn" in x else str(x)
    except ValueError:
        pass
    return choice


def _is_placeholder_bucket(name: str) -> bool:
    s = (name or "").strip()
    return not s or s == TERRAFORM_STATE_BUCKET_PLACEHOLDER


def _is_placeholder_role(arn: str) -> bool:
    a = (arn or "").strip()
    return not a or AWS_ROLE_ARN_PLACEHOLDER_ACCOUNT in a


def _effective_current(current: dict, key: str, placeholder_check=None) -> str:
    val = current.get(key, "")
    if placeholder_check and placeholder_check(val):
        return ""
    return val or ""


def read_current_config() -> dict:
    current = {}
    g = _parse_export_file(CONFIG_GLOBAL)
    if g:
        current["app_name"] = g.get("APP_IDENT_WITHOUT_ENV", "")
        current["terraform_state_bucket"] = g.get("TERRAFORM_STATE_BUCKET", "")
        current["aws_region"] = g.get("AWS_DEFAULT_REGION", "us-west-2")
        current["aws_role_arn"] = g.get("AWS_ROLE_ARN", "")
        current["app_cpu"] = g.get("APP_CPU", "256")
        current["app_memory"] = g.get("APP_MEMORY", "512")
        current["launch_type"] = g.get("LAUNCH_TYPE", "FARGATE")
        current["cpu_architecture"] = g.get("CPU_ARCHITECTURE", "X86_64")
        current["trigger_type"] = g.get("trigger_type", "ecs_eventbridge")
        current["vpc_name"] = g.get("VPC_NAME", "")
    s = _parse_export_file(CONFIG_STAGING)
    if s:
        current["api_root_domain"] = s.get("API_ROOT_DOMAIN", "")
        current["api_domain_staging"] = s.get("API_DOMAIN", "")
        current["min_count"] = s.get("MIN_COUNT", "1")
        current["max_count_staging"] = s.get("MAX_COUNT", "2")
    p = _parse_export_file(CONFIG_PROD)
    if p:
        current["api_domain_prod"] = p.get("API_DOMAIN", "")
        current["max_count_prod"] = p.get("MAX_COUNT", "2")
    return current


def write_config_global(args: argparse.Namespace) -> None:
    vpc_line = ""
    if getattr(args, "vpc_name", ""):
        vpc_line = "export VPC_NAME={}\n".format(args.vpc_name)
    else:
        vpc_line = "# export VPC_NAME=my-standard-vpc\n"
    content = """#########################################################
# Configuration
#########################################################
# Used to identify the application in AWS resources | allowed characters: a-zA-Z0-9-_
# NOTE: This must be no longer than 20 characters long
export APP_IDENT_WITHOUT_ENV={app_name}
export APP_IDENT="${{APP_IDENT_WITHOUT_ENV}}-${{ENVIRONMENT}}"
export TERRAFORM_STATE_IDENT=$APP_IDENT

# This is the AWS S3 bucket in which you are storing your terraform state files
# - This must exist before deploying
export TERRAFORM_STATE_BUCKET={terraform_state_bucket}

# This is the AWS region in which the application will be deployed
export AWS_DEFAULT_REGION={aws_region}

# OIDC Deployment role
export AWS_ROLE_ARN={aws_role_arn}
export AWS_WEB_IDENTITY_TOKEN_FILE=$(pwd)/web-identity-token

# ECS Task cpu and memory settings
export APP_CPU={app_cpu}  # cpu
export APP_MEMORY={app_memory}  # memory in MB

# This is either EC2, FARGATE, or FARGATE_SPOT
export LAUNCH_TYPE={launch_type}

# Must be one of these: X86_64, ARM64
# NOTE: If deploying to EC2 you must choose the same architecture as your instances
# NOTE2: Only GitHub supports ARM64 builds - Bitbucket doesn't
# NOTE3: In GitHub the build by default will be slow on ARM64. To speed this up,
#        create an ARM64 GitHub-hosted runner and use that instead.
export CPU_ARCHITECTURE={cpu_architecture}

# ECS trigger: ecs_eventbridge (scheduled) or ecs_api_service (ALB + service).
# Set in config.<env> to override. Use "none" only for internal two-phase apply.
export trigger_type={trigger_type}

# Optional: set VPC_NAME to a tag:Name value to use a custom VPC; leave unset for default VPC
{vpc_line}
#########################################################
# Create code hash
# NOTE:
#   - When the code changes a new code hash file should be created
#   - The find command here should be configured so that it finds all files such that if they change a re-build
#     and deploy should occur
#########################################################
export CODE_HASH_FILE=code_hash.txt
docker run --rm -v $(pwd):/workdir -w /workdir alpine sh -c \\
  "apk add --no-cache findutils coreutils && \\
   find . -type f -path './.git*' -prune -o -path './.github*' -prune -o \\( -name '*.go' -o -name '*.sh' -o -name 'Dockerfile' -o -name 'go.mod' -o -name 'go.sum' -o -name 'config.*' \\) \\
   -exec md5sum {{}} + | sort | md5sum | cut -d ' ' -f1 > terraform/main/${{CODE_HASH_FILE}}"
"""
    with open(CONFIG_GLOBAL, "w", encoding="utf-8") as f:
        f.write(content.format(
            app_name=args.app_name,
            terraform_state_bucket=args.terraform_state_bucket,
            aws_region=args.aws_region,
            aws_role_arn=args.aws_role_arn,
            app_cpu=args.app_cpu,
            app_memory=args.app_memory,
            launch_type=args.launch_type,
            cpu_architecture=args.cpu_architecture,
            trigger_type=args.app_type,
            vpc_line=vpc_line,
        ))
    print("Wrote config.global")


def write_config_staging(args: argparse.Namespace) -> None:
    api_root = getattr(args, "api_root_domain", "") or "example.com"
    api_staging = getattr(args, "api_domain_staging", "") or "api-staging.example.com"
    api_block = """
####################################################################################################
# API Service Configuration
# * You only need these if you are running your project as a service api
# * NOTE: The root domain MUST already exist in Route53 in your AWS account for this to work
####################################################################################################
export API_ROOT_DOMAIN={api_root_domain}
export API_DOMAIN={api_domain_staging}
"""
    content = """# NOTE: Variables set in here will activate only in a staging environment
# export EXAMPLE_VAR="Hello from staging"
""" + api_block + """
# Number of tasks in an ECS Service
export MIN_COUNT={min_count}
export MAX_COUNT={max_count}
"""
    with open(CONFIG_STAGING, "w", encoding="utf-8") as f:
        f.write(content.format(
            api_root_domain=api_root,
            api_domain_staging=api_staging,
            min_count=getattr(args, "min_count", "1"),
            max_count=getattr(args, "max_count_staging", "2"),
        ))
    print("Wrote config.staging")


def write_config_prod(args: argparse.Namespace) -> None:
    api_root = getattr(args, "api_root_domain", "") or "example.com"
    api_prod = getattr(args, "api_domain_prod", "") or "api.example.com"
    api_block = """
####################################################################################################
# API Service Configuration
# * You only need these if you are running your project as a service api
# * NOTE: The root domain MUST already exist in Route53 in your AWS account for this to work
####################################################################################################
export API_ROOT_DOMAIN={api_root_domain}
export API_DOMAIN={api_domain_prod}
"""
    content = """# NOTE: Variables set in here will activate only in a production environment
# export EXAMPLE_VAR="Hello from production"
""" + api_block + """
# Number of tasks in an ECS Service
export MIN_COUNT={min_count}
export MAX_COUNT={max_count}
"""
    with open(CONFIG_PROD, "w", encoding="utf-8") as f:
        f.write(content.format(
            api_root_domain=api_root,
            api_domain_prod=api_prod,
            min_count=getattr(args, "min_count", "1"),
            max_count=getattr(args, "max_count_prod", "2"),
        ))
    print("Wrote config.prod")


def apply_go_mod_module(app_name: str) -> None:
    """Set go.mod module line to match APP_IDENT_WITHOUT_ENV (app_name)."""
    if not app_name or not os.path.isfile(GO_MOD_PATH):
        return
    with open(GO_MOD_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith("module "):
            lines[i] = "module {}\n".format(app_name.strip())
            break
    with open(GO_MOD_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Updated go.mod module to {}".format(app_name))


def apply_main_go_for_trigger(trigger_type: str) -> None:
    """Enable Fiber API or EventBridge main.go so deployed app matches trigger_type."""
    if not os.path.isfile(MAIN_GO_PATH):
        return
    content = MAIN_GO_FIBER if trigger_type == "ecs_api_service" else MAIN_GO_EVENTBRIDGE
    with open(MAIN_GO_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    if trigger_type == "ecs_api_service":
        print("Enabled Fiber API in cmd/app/main.go (/:8080, /healthcheck for ALB)")
    else:
        print("Enabled EventBridge/scheduled main in cmd/app/main.go")


def prompt(msg: str, default: str = "") -> str:
    if default:
        s = input("{} [{}]: ".format(msg, default)).strip()
        return s if s else default
    while True:
        s = input("{}: ".format(msg)).strip()
        if s:
            return s


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure this AWS ECS project for app type and AWS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--app-type",
        choices=APP_TYPES,
        help="App type: ecs_api_service (ALB+service), ecs_background_service, ecs_eventbridge (scheduled)",
    )
    parser.add_argument("--app-name", default="", help="APP_IDENT_WITHOUT_ENV (max 20 chars)")
    parser.add_argument("--terraform-state-bucket", default="", help="S3 bucket for Terraform state")
    parser.add_argument("--aws-region", default="us-west-2", help="AWS region")
    parser.add_argument("--aws-role-arn", default="", help="OIDC deployment role ARN for CI/CD")
    parser.add_argument("--app-cpu", default="256", help="ECS task CPU units (256,512,1024,...)")
    parser.add_argument("--app-memory", default="512", help="ECS task memory MB")
    parser.add_argument("--launch-type", default="FARGATE", choices=("FARGATE", "FARGATE_SPOT", "EC2"))
    parser.add_argument("--cpu-architecture", default="X86_64", choices=("X86_64", "ARM64"))
    parser.add_argument("--vpc-name", default="", help="Optional VPC tag:Name")
    parser.add_argument("--api-root-domain", default="", help="Root domain for API (ecs_api_service only)")
    parser.add_argument("--api-domain-staging", default="", help="API domain for staging")
    parser.add_argument("--api-domain-prod", default="", help="API domain for prod")
    parser.add_argument("--min-count", default="1", help="MIN_COUNT for ECS service")
    parser.add_argument("--max-count-staging", default="2", help="MAX_COUNT for staging")
    parser.add_argument("--max-count-prod", default="2", help="MAX_COUNT for prod")
    parser.add_argument("--non-interactive", action="store_true", help="Fail if required args missing")
    args = parser.parse_args()

    if not args.non_interactive:
        print("AWS credentials (used to discover Terraform bucket, OIDC role, etc.)")
        prompt_for_aws_credentials()
    ensure_aws_credentials()
    current = read_current_config()
    region = args.aws_region or current.get("aws_region", "us-west-2")

    discovered = discover_aws_resources(region)
    if discovered["oidc_roles"] or discovered["terraform_buckets"] or discovered["route53_domains"]:
        print("Discovered AWS resources (you can select by number or enter manually).")

    if not args.non_interactive:
        effective_role = _effective_current(current, "aws_role_arn", _is_placeholder_role)
        effective_bucket = _effective_current(current, "terraform_state_bucket", _is_placeholder_bucket)
        if not args.aws_role_arn and effective_role:
            args.aws_role_arn = effective_role
        if not args.aws_role_arn and discovered["oidc_roles"]:
            args.aws_role_arn = _choose_from_list("OIDC role (GitHub Actions):", discovered["oidc_roles"])
        elif not args.aws_role_arn:
            args.aws_role_arn = prompt("OIDC role ARN", effective_role)

        if not args.terraform_state_bucket and effective_bucket:
            args.terraform_state_bucket = effective_bucket
        if not args.terraform_state_bucket and discovered["terraform_buckets"]:
            args.terraform_state_bucket = _choose_from_list("Terraform state bucket:", discovered["terraform_buckets"])
        elif not args.terraform_state_bucket:
            args.terraform_state_bucket = prompt("Terraform state bucket", effective_bucket)

        if not args.app_name:
            args.app_name = prompt("App name (APP_IDENT_WITHOUT_ENV, max 20 chars)", current.get("app_name", ""))
        if not args.app_type:
            args.app_type = prompt("App type (ecs_api_service | ecs_background_service | ecs_eventbridge)", current.get("trigger_type", "ecs_eventbridge"))
            if args.app_type not in APP_TYPES:
                args.app_type = "ecs_eventbridge"

        for attr, default in [
            ("app_cpu", current.get("app_cpu", "256")),
            ("app_memory", current.get("app_memory", "512")),
            ("launch_type", current.get("launch_type", "FARGATE")),
            ("cpu_architecture", current.get("cpu_architecture", "X86_64")),
            ("aws_region", current.get("aws_region", "us-west-2")),
        ]:
            if not getattr(args, attr):
                setattr(args, attr, default)

        if args.app_type == "ecs_api_service":
            if not args.api_root_domain and discovered["route53_domains"]:
                args.api_root_domain = _choose_from_list("API root domain (Route53):", discovered["route53_domains"])
            if not args.api_root_domain:
                args.api_root_domain = prompt("API root domain (must exist in Route53)", current.get("api_root_domain", "example.com"))
            if not args.api_domain_staging:
                args.api_domain_staging = prompt("API domain for staging", current.get("api_domain_staging", "api-staging." + args.api_root_domain))
            if not args.api_domain_prod:
                args.api_domain_prod = prompt("API domain for prod", current.get("api_domain_prod", "api." + args.api_root_domain))

        if not getattr(args, "min_count", ""):
            args.min_count = current.get("min_count", "1")
        if not getattr(args, "max_count_staging", ""):
            args.max_count_staging = current.get("max_count_staging", "2")
        if not getattr(args, "max_count_prod", ""):
            args.max_count_prod = current.get("max_count_prod", "2")
        if not getattr(args, "vpc_name", ""):
            args.vpc_name = current.get("vpc_name", "")
    else:
        required = [("app_name", "App name"), ("terraform_state_bucket", "Terraform state bucket"), ("aws_role_arn", "OIDC role ARN")]
        for attr, desc in required:
            if not getattr(args, attr):
                print("Error: {} required. Set --{} or run without --non-interactive.".format(desc, attr.replace("_", "-")), file=sys.stderr)
                return 1
        if not args.app_type:
            args.app_type = current.get("trigger_type", "ecs_eventbridge")
        if args.app_type not in APP_TYPES:
            args.app_type = "ecs_eventbridge"
        defaults = {"app_cpu": "256", "app_memory": "512", "launch_type": "FARGATE", "cpu_architecture": "X86_64"}
        for attr in ("app_cpu", "app_memory", "launch_type", "cpu_architecture"):
            if not getattr(args, attr):
                setattr(args, attr, current.get(attr, defaults.get(attr)))
        if args.app_type == "ecs_api_service":
            args.api_root_domain = args.api_root_domain or current.get("api_root_domain", "example.com")
            args.api_domain_staging = args.api_domain_staging or current.get("api_domain_staging", "api-staging.example.com")
            args.api_domain_prod = args.api_domain_prod or current.get("api_domain_prod", "api.example.com")
        args.min_count = getattr(args, "min_count", None) or "1"
        args.max_count_staging = getattr(args, "max_count_staging", None) or "2"
        args.max_count_prod = getattr(args, "max_count_prod", None) or "2"
        args.vpc_name = getattr(args, "vpc_name", None) or ""

    write_config_global(args)
    write_config_staging(args)
    write_config_prod(args)
    apply_go_mod_module(args.app_name)
    apply_main_go_for_trigger(args.app_type)
    print("Setup complete. Edit config.global (and config.staging/config.prod) if needed, then deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

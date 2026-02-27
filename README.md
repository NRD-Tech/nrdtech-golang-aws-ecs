# Golang AWS ECS App

Template for a Golang application running on AWS ECS. The app can be run in one of two modes, selected by **trigger_type**: scheduled runs via EventBridge or an always-on API behind an Application Load Balancer.

For a **detailed workflow and concept guide** (ECS, tasks, task definition, IAM, deployment and runtime flows with diagrams), see **[ARCHITECTURE.md](ARCHITECTURE.md)**.

# Technology Stack

- Golang 1.24.3
- Docker
- Terraform

# Architecture

## Overview

- **ECS Fargate** (or FARGATE_SPOT / EC2): tasks run in a single ECS cluster. Image is built and pushed to **ECR**; Terraform manages the task definition, cluster, and trigger-specific resources.
- **Shared resources** (always created): ECS cluster, ECR repository, task definition, task IAM roles, CloudWatch log group.
- **Trigger-specific resources** are created only when the matching `trigger_type` is set; the other trigger's resources are not created. No Terraform files are commented out—selection is done via the `trigger_type` variable.

## Trigger: EventBridge (scheduled) — `trigger_type = "ecs_eventbridge"`

- **Use case:** Batch or cron-style workloads that run on a schedule.
- **Resources:** CloudWatch Events rule (schedule), EventBridge target (run ECS task), SQS DLQ for failed invocations, IAM role for Events to run tasks.
- **Behaviour:** The rule triggers the ECS cluster to run the task definition; no long-lived ECS service. Schedule can be enabled/disabled per environment (e.g. disabled in staging, enabled in prod).

## Trigger: API service (ALB) — `trigger_type = "ecs_api_service"`

- **Use case:** HTTP API or web service that must be always available.
- **Resources:** ECS service (desired count ≥ 1), Application Load Balancer, target group, security groups (ECS + ALB), optional auto-scaling. Optionally: ACM certificate, Route53 record, HTTPS listener when `API_DOMAIN` / `API_ROOT_DOMAIN` are set.
- **Behaviour:** ALB forwards traffic to the ECS service; tasks listen on port 8080 (e.g. `/healthcheck` for ALB health checks).

# Trigger type mechanism

- **Variable:** `trigger_type` is set in `config.global` or overridden in `config.<env>` (e.g. `config.staging`, `config.prod`). Valid values:
  - `ecs_eventbridge` — EventBridge schedule (default).
  - `ecs_api_service` — ALB + ECS service.
- **Terraform:** `terraform/main/ecs_eventbridge.tf` and `terraform/main/ecs_api_service.tf` both remain in the repo. Each resource uses `count` or a local (e.g. `local.ecs_eventbridge_enabled`, `local.ecs_api_service_enabled`) so that only the chosen trigger's resources are created.
- **Switching triggers:** Change `trigger_type` in config and re-deploy. If Terraform reports a cycle (e.g. when moving between trigger types), the apply script runs a **two-phase apply**: it temporarily sets `trigger_type = "none"` (creating neither trigger), applies, then restores your chosen value and applies again. No manual state edits or file uncommenting.
- **API service options:** When using `ecs_api_service`, set `API_DOMAIN` and `API_ROOT_DOMAIN` in `config.<env>` if you want a custom domain and HTTPS; otherwise the ALB is available by its DNS name on HTTP only.

# Setting Up Your Development Environment

## Clone and Clean the template (if using GitHub)

- Navigate to the template repo (e.g. NRD-Tech/nrdtech-golang-aws-ecs or your fork).
- Log into your GitHub account (otherwise the "Use this template" option will not show up).
- Click "Use this template" → Create a new repository.
- Clone your newly created repository.
- If you want to change the license to be proprietary: [Go to Proprietary Licensing Section](#how-to-use-this-template-for-a-proprietary-project).

## Clone and Clean the template (if NOT using GitHub)

```
git clone <template-repo-url> my-project
cd my-project
rm -fR .git .idea
git init
git add .
git commit -m 'init'
```

- If you want to change the license to be proprietary follow these instructions: [Go to Proprietary Licensing Section](#how-to-use-this-template-for-a-proprietary-project)

# Configuring the App for AWS Deployment

## OIDC Pre-Requisite

- You must have previously set up the AWS Role for OIDC and S3 bucket for the Terraform state files
- The easiest way to do this is to use the NRD-Tech Terraform Bootstrap template
  - [https://github.com/NRD-Tech/nrdtech-terraform-aws-account-bootstrap](https://github.com/NRD-Tech/nrdtech-terraform-aws-account-bootstrap)
  - After following the README.md instructions in the bootstrap template project you should have:
    - An AWS Role ARN
    - An AWS S3 bucket for the Terraform state files

## AWS Pre-Requisite

- Configure VPC Subnets with names that have "private" or "public" in them
  - Examples:
    - public-subnet-west-2a
    - private-subnet-west-2a
  - Terraform uses this to determine in which subnets to deploy the tasks

## Configure Settings

- Edit config.global
  - At a minimum set:
    - APP_IDENT_WITHOUT_ENV
    - TERRAFORM_STATE_BUCKET
    - AWS_DEFAULT_REGION
    - AWS_ROLE_ARN
    - LAUNCH_TYPE — one of EC2, FARGATE, or FARGATE_SPOT (EC2 requires an ECS cluster with an EC2 capacity provider)
    - **trigger_type** — `ecs_eventbridge` (scheduled) or `ecs_api_service` (ALB + service). See [Architecture](#architecture) and [Trigger type mechanism](#trigger-type-mechanism).
  - Optional: set `VPC_NAME` to a VPC tag name for a custom VPC; leave unset for the default VPC.
- Edit go.mod — set the module name (e.g. same as APP_IDENT_WITHOUT_ENV).
- For **ecs_eventbridge**: ensure your app and Dockerfile support a short-lived task (run and exit). For **ecs_api_service**: ensure the app exposes HTTP on port 8080 (e.g. `/healthcheck` for the ALB) and add Fiber if needed: `go get github.com/gofiber/fiber/v2`.

* Commit your changes to git

```
git add .
git commit -a -m 'updated config'
```

## Enable GitHub Flow Deployment (Default and Preferred Method)

**Note:** The workflow file `.github/workflows/github_flow.yml` is included and active. It reads configuration from `config.global` and `config.<env>` (no manual editing of the workflow needed).

The GitHub Flow workflow will:

- Run tests on all pushes and pull requests to `main`
- Deploy to **staging** on push to `main` (using `config.global` and `config.staging`; **trigger_type** and other vars are read from these)
- Deploy to **production** when a version tag (e.g. `v1.0.0`) is pushed (using `config.prod`)
- Run **destroy** for an environment when a destroy tag is pushed: `destroy-staging-*` or `destroy-prod-*`

### Deploy to Staging

Simply push your changes to the `main` branch:

```
git push origin main
```

The workflow will automatically deploy to staging after tests pass.

### Deploy to Production

Create and push a version tag:

```
git tag v1.0.0
git push origin v1.0.0
```

The workflow will automatically deploy to production after tests pass.

### Testing the API after deploy (trigger_type = ecs_api_service)

1. **Get the API URL**
   - If you set **API_DOMAIN** in config (e.g. `api-staging.mycompany.com`): use `https://<API_DOMAIN>`.
   - Otherwise, from the project root (with env and AWS set up), run:
     ```bash
     cd terraform/main && terraform output -raw api_base_url
     ```
   - Or in AWS Console: EC2 → Load Balancers → select the `*-alb` → copy DNS name; use `http://<dns-name>`.

2. **Check health (ALB relies on this)**
   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://api-staging.mycompany.com/healthcheck
   ```
   Expect `200`. The ALB health check is configured for `GET /healthcheck` → 200; your app must expose that route.

3. **Hit other routes**
   ```bash
   curl https://api-staging.mycompany.com/
   curl https://api-staging.mycompany.com/ping
   ```
   Replace the host with your API_DOMAIN or ALB DNS. If the template's Fiber routes are still commented out in `cmd/app/main.go`, uncomment the API service block and add a `GET /healthcheck` handler that returns 200 so the ALB can mark targets healthy.

### Testing EventBridge deploy (trigger_type = ecs_eventbridge)

Run one task manually in the ECS cluster (AWS Console: ECS → Clusters → your cluster → Run new task, or use `aws ecs run-task`), then check CloudWatch Logs for the log group `/ecs/<APP_IDENT>` to confirm the container ran.

## (Alternative: If using Bitbucket) Enable Bitbucket Pipeline

- Push your git project up into a new Bitbucket project
- Navigate to your project on Bitbucket
  - Click Repository Settings
  - Click Pipelines->Settings
    - Click Enable Pipelines
- Deploy to Staging:
  ```
  git checkout -b staging
  git push --set-upstream origin staging
  ```
- Deploy to Production:
  ```
  git checkout -b production
  git push --set-upstream origin production
  ```

## Un-Deploying

### Un-Deploying with GitHub Flow

- **Via tags (recommended):** Push a destroy tag to run the destroy job in the workflow.
  - Staging: `git tag destroy-staging-1 && git push origin destroy-staging-1`
  - Production: `git tag destroy-prod-1 && git push origin destroy-prod-1`
- **Manually:** Run the destroy script locally (with AWS credentials and env loaded):
  - Staging: `ENVIRONMENT=staging ./deploy.sh -d`
  - Production: `ENVIRONMENT=prod ./deploy.sh -d`

### Un-Deploying in Bitbucket

1. Navigate to the Bitbucket project website
2. Click Pipelines in the left nav menu
3. Click Run pipeline button
4. Choose the branch you want to un-deploy
5. Choose the appropriate un-deploy Pipeline
   - un-deploy-staging
   - un-deploy-production
6. Click Run

# Misc How-To's

## How to use this template for a proprietary project

This project's license (MIT License) allows for you to create proprietary code based on this template.

Here are the steps to correctly do this:

1. Replace the LICENSE file with your proprietary license terms if you wish to use your own license.
2. Optionally, include a NOTICE file stating that the original work is licensed under the MIT License and specify the parts of the project that are governed by your proprietary license.

## How to run the Docker image locally

```
aws ecr get-login-password --region <AWS_REGION> | \
  docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com

docker run --rm -p 8080:8080 <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/<APP_IDENT>_repository:latest
```

Then open `http://localhost:8080` (and e.g. `http://localhost:8080/healthcheck` for the API service trigger).

## How to inspect the Docker image

```
alias dive="docker run -ti --rm -v /var/run/docker.sock:/var/run/docker.sock wagoodman/dive"
dive <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/<APP_IDENT>_repository:latest
```

## How to view image architecture and metadata

After logging in to ECR (see above), run `docker pull` and `docker inspect` with your repository URL.

# Appendix

## Product Structure

```
project-name/
├── cmd/                  # Main applications for this project
│   ├── app1/
│   │   └── main.go       # Entry point for app1
│   └── app2/
│       └── main.go       # Entry point for app2 (if multiple binaries)
├── pkg/                  # Library code that's safe to be imported by other projects
│   ├── utils/            # Reusable utility functions
│   ├── errors/           # Centralized error handling
│   └── logger/           # Logging utilities
├── internal/             # Private application code (not importable outside this project)
│   ├── app/              # Application-specific code (business logic)
│   ├── config/           # Configuration handling
│   ├── db/               # Database access logic
│   ├── server/           # HTTP server setup
│   └── routes/           # Router and route handlers
├── api/                  # API definitions (Swagger/OpenAPI, gRPC, etc.)
│   └── openapi.yaml      # Example: OpenAPI spec file
├── migrations/           # Database migration files (if using SQL-based DBs)
├── web/                  # Static assets for a web UI, if applicable
│   ├── html/
│   ├── css/
│   └── js/
├── test/                 # Additional external test data and helpers
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── vendor/               # Optional: vendored dependencies (auto-managed by `go mod vendor`)
├── scripts/              # Helper scripts (build, run, CI/CD)
│   ├── build.sh
│   └── test.sh
├── Makefile              # Build and management commands
├── go.mod                # Go module definition
├── go.sum                # Go module dependencies checksum
└── README.md             # Project overview and documentation
```

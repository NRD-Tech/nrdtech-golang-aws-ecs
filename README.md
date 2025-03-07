# Python AWS Lambda App
This is a project template for a golang application that can be triggered either by an Event Bridge scheduled rule or an API via a load balancer. 

# Technology Stack
* Golang 1.23.3
* Docker
* Terraform

# Setting Up Your Development Environment

## Clone and Clean the template (if using GitHub)
* Navigate to: https://github.com/NRD-Tech/nrdtech-golang-aws-lambda.git
* Log into your GitHub account (otherwise the "Use this template" option will not show up)
* Click "Use this template" in the top right corner
  * Create a new repository
* Fill in your repository name, description, and public/private setting
* Clone your newly created repository
* If you want to change the license to be proprietary follow these instructions: [Go to Proprietary Licensing Section](#how-to-use-this-template-for-a-proprietary-project)

## Clone and Clean the template (if NOT using GitHub)
```
git clone https://github.com/NRD-Tech/nrdtech-golang-aws-lambda.git my-project
cd my-project
rm -fR .git venv .idea
git init
git add .
git commit -m 'init'
```
* If you want to change the license to be proprietary follow these instructions: [Go to Proprietary Licensing Section](#how-to-use-this-template-for-a-proprietary-project)

# Configuring the App for AWS Deployment

## OIDC Pre-Requisite
* You must have previously set up the AWS Role for OIDC and S3 bucket for the Terraform state files
* The easiest way to do this is to use the NRD-Tech Terraform Bootstrap template
  * https://github.com/NRD-Tech/nrdtech-terraform-aws-account-bootstrap
  * After following the README.md instructions in the bootstrap template project you should have:
    * An AWS Role ARN
    * An AWS S3 bucket for the Terraform state files

## AWS Pre-Requisite
* Configure VPC Subnets with names that have "private" or "public" in them
  * Examples:
    * public-subnet-west-2a
    * private-subnet-west-2a
  * Terraform uses this to determine in which subnets to deploy the tasks

## Configure Settings
* Edit .env.global
  * Each config is a little different per application but at a minimum you will need to change:
    * APP_IDENT_WITHOUT_ENV
    * TERRAFORM_STATE_BUCKET
    * AWS_DEFAULT_REGION
    * AWS_ROLE_ARN
    * ECS_CLUSTER_ARN
      * Choose an existing ECS Cluster to use
    * LAUNCH_TYPE
      * Specify one of these launch types: EC2, FARGATE, or FARGATE_SPOT
      * Note that for the EC2 option to work you must choose an ECS Cluster that has an EC2 Capacity Provider
* Edit go.mod
  * Set an appropriate module name (likely the same as APP_IDENT_WITHOUT_ENV)
* Choose how your Task will be triggered
  * Event Bridge Scheduling:
    * Un-comment terraform/main/ecs_eventbridge.tf
    * Edit app/main.go to enable the appropriate section
    * Edit Dockerfile at the bottom to start your task correctly
  * ECS Service (always-on running service with 1+ tasks)
    * Un-comment terraform/main/ecs_service.tf
    * Edit app/main.go to enable the appropriate section
    * Install Fiber dependencies: `go get github.com/gofiber/fiber/v2`
* Choose which VPC to use, specify that vpc in `terraform/main/main.tf`

* Commit your changes to git
```
git add .
git commit -a -m 'updated config'
```

## (If using Bitbucket) Enable Bitbucket Pipeline (NOTE: GitHub does not require any setup like this for the Actions to work)
* Push your git project up into a new Bitbucket project
* Navigate to your project on Bitbucket
  * Click Repository Settings
  * Click Pipelines->Settings
    * Click Enable Pipelines

## (If using GitHub) Configure the AWS Role
* Edit .github/workflows/main.yml
    * Set the pipeline role for role-to-assume
      * This should be the same as the AWS_ROLE_ARN in your .env.global
    * Set the correct aws-region

## Deploy to Staging
```
git checkout -b staging
git push --set-upstream origin staging
```

## Deploy to Production
```
git checkout -b production
git push --set-upstream origin production
```

## Un-Deploying in Bitbucket
1. Navigate to the Bitbucket project website
2. Click Pipelines in the left nav menu
3. Click Run pipeline button
4. Choose the branch you want to un-deploy
5. Choose the appropriate un-deploy Pipeline
   * un-deploy-staging
   * un-deploy-production
6. Click Run

# Misc How-To's

## How to use this template for a proprietary project
This project's license (MIT License) allows for you to create proprietary code based on this template.

Here are the steps to correctly do this:
1. Replace the LICENSE file with your proprietary license terms if you wish to use your own license.
2. Optionally, include a NOTICE file stating that the original work is licensed under the MIT License and specify the parts of the project that are governed by your proprietary license.

## How To run docker image locally
```
aws ecr get-login-password \
      --region us-west-2 | \
      docker login \
        --username AWS \
        --password-stdin 1234567890.dkr.ecr.us-west-2.amazonaws.com/my-test-project-prod_repository

docker run --rm -p 9000:8080 -it 1234567890.dkr.ecr.us-west-2.amazonaws.com/myapp_lambda_repository:latest 

curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'

```

# How To Inspect docker image
```
alias dive="docker run -ti --rm  -v /var/run/docker.sock:/var/run/docker.sock wagoodman/dive"
dive 1234567890.dkr.ecr.us-west-2.amazonaws.com/myapp_lambda_repository:latest
```

# How to view the architecture (and other info) of a docker image
```
export AWS_PROFILE=mycompanyprofile
docker logout 1234567890.dkr.ecr.us-west-2.amazonaws.com
aws ecr get-login-password \
      --region us-west-2 | \
      docker login \
        --username AWS \
        --password-stdin 1234567890.dkr.ecr.us-west-2.amazonaws.com/myapp_lambda_repository
docker pull 1234567890.dkr.ecr.us-west-2.amazonaws.com/myapp_lambda_repository
docker inspect 1234567890.dkr.ecr.us-west-2.amazonaws.com/myapp_lambda_repository
```

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

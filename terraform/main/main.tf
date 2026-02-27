terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.81.0"
    }
  }
}

provider "aws" {
  region  = var.AWS_REGION
  default_tags {
    tags = data.terraform_remote_state.app_bootstrap.outputs.app_tags
  }
}

# Sometimes we specifically need us-east-1 for some resources
provider "aws" {
  alias  = "useast1"
  region = "us-east-1"
  default_tags {
    tags = data.terraform_remote_state.app_bootstrap.outputs.app_tags
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

#############################
# VPC: default when VPC_NAME is empty, else lookup by tag Name
#############################
data "aws_vpc" "selected" {
  count  = var.VPC_NAME != "" ? 1 : 0
  filter {
    name   = "tag:Name"
    values = [var.VPC_NAME]
  }
}

data "aws_vpc" "selected_default" {
  count   = var.VPC_NAME == "" ? 1 : 0
  default = true
}

locals {
  vpc_id = var.VPC_NAME != "" ? data.aws_vpc.selected[0].id : data.aws_vpc.selected_default[0].id
}

data "aws_subnets" "subnets" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
  filter {
    name   = "tag:Name"
    values = ["*public*"]
  }
}
data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
  filter {
    name   = "tag:Name"
    values = ["*private*"]
  }
}
data "aws_route_tables" "private" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "association.subnet-id"
    values = data.aws_subnets.private.ids
  }
}

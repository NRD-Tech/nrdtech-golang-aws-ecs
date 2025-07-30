variable "AWS_REGION" {
  type = string
}

variable "APP_IDENT" {
  description = "Identifier of the application"
  type        = string
}

variable "APP_IDENT_WITHOUT_ENV" {
    description = "Identifier of the application that doesn't include the environment"
    type = string
}

variable "ENVIRONMENT" {
  type        = string
}

variable "CODE_HASH_FILE" {
  description = "Filename of the code hash file"
  type        = string
}

variable "LAUNCH_TYPE" {
  description = "Launch type for ECS (FARGATE, FARGATE_SPOT, or EC2)"
  default     = "FARGATE"
}

variable "APP_CPU" {
  description = "ECS CPU"
  type        = number
}

variable "APP_MEMORY" {
  description = "ECS Memory"
  type        = number
}

variable "DESIRED_COUNT" {
  description = "Number of desired instances for a service task"
  type = number
  default = 1
}

variable "CPU_ARCHITECTURE" {
  description = "X86_64 or ARM64"
  type = string
}

##################################################
# API Gateway variables
##################################################
variable "API_DOMAIN" {
  type = string
}

variable "API_ROOT_DOMAIN" {
  type = string
}

##################################################
# Code Artifact
##################################################
variable "CODEARTIFACT_TOKEN" {
  description = "CodeArtifact token for authentication"
  type        = string
  default = ""
}

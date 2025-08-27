resource "aws_ecs_cluster" "ecs" {
  name = var.APP_IDENT

  setting {
    name  = "containerInsights"
    value = "enabled" # could also be: disabled or enhanced
  }
}

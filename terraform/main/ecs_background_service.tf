# locals {
#   # 1. Define each capacity provider strategy as a list
#   #    so Terraform doesn't see them as "tuple of length 1 vs 2 vs 0"
#   fargate_strategy = tolist([
#     {
#       capacity_provider = "FARGATE"
#       weight            = 1
#     }
#   ])

#   fargate_spot_strategy = tolist([
#     {
#       capacity_provider = "FARGATE"
#       weight            = 3
#     },
#     {
#       capacity_provider = "FARGATE_SPOT"
#       weight            = 7
#     }
#   ])

#   ec2_strategy = tolist([
#     {
#       capacity_provider = "EC2"
#       weight            = 1
#     }
#   ])

#   # 2. Define your local "ecs_target" by picking one of the above
#   ecs_target = {
#     capacity_provider_strategy = (
#       var.LAUNCH_TYPE == "FARGATE" ? local.fargate_strategy :
#       var.LAUNCH_TYPE == "FARGATE_SPOT" ? local.fargate_spot_strategy :
#       local.ec2_strategy
#     )

#     # network configuration depends on whether it's Fargate or not
#     network_configuration = (
#       var.LAUNCH_TYPE == "FARGATE" || var.LAUNCH_TYPE == "FARGATE_SPOT"
#         ? {
#             security_groups  = [aws_security_group.ecs_sg.id]
#             subnets          = data.aws_subnets.public.ids
#             assign_public_ip = true
#           }
#         : {
#             security_groups = [aws_security_group.ecs_sg.id]
#             subnets = data.aws_subnets.public.ids
#             assign_public_ip = false
#           }
#     )
#   }
# }

# locals {
#   cluster_name = element(split("/", aws_ecs_cluster.ecs.arn), 1)
# }

# data "aws_ecs_cluster" "cluster" {
#   cluster_name = local.cluster_name
# }

# # ECS Service for background processing
# resource "aws_ecs_service" "ecs_service" {
#   name            = "${var.APP_IDENT}-service"
#   cluster         = aws_ecs_cluster.ecs.arn
#   task_definition = aws_ecs_task_definition.task_definition.arn
#   desired_count   = var.DESIRED_COUNT
#   deployment_maximum_percent         = 200
#   deployment_minimum_healthy_percent = 100

#   dynamic "capacity_provider_strategy" {
#     for_each = local.ecs_target.capacity_provider_strategy
#     content {
#       capacity_provider = capacity_provider_strategy.value.capacity_provider
#       weight            = capacity_provider_strategy.value.weight
#     }
#   }

#   dynamic "network_configuration" {
#     for_each = local.ecs_target.network_configuration != null ? [1] : []
#     content {
#       security_groups  = local.ecs_target.network_configuration.security_groups
#       subnets          = local.ecs_target.network_configuration.subnets
#       assign_public_ip = local.ecs_target.network_configuration.assign_public_ip
#     }
#   }

#   deployment_controller {
#     type = "ECS"
#   }

#   lifecycle {
#     create_before_destroy = true
#   }
# }

# resource "aws_appautoscaling_target" "ecs_target" {
#   max_capacity       = 2  # Configure this to something appropriate for your application
#   min_capacity       = 1  # Configure this to something appropriate for your application
#   resource_id        = "service/${local.cluster_name}/${aws_ecs_service.ecs_service.name}"
#   scalable_dimension = "ecs:service:DesiredCount"
#   service_namespace  = "ecs"
# }

# resource "aws_appautoscaling_policy" "scale_out" {
#   name                   = "scale-out"
#   service_namespace      = aws_appautoscaling_target.ecs_target.service_namespace
#   resource_id            = aws_appautoscaling_target.ecs_target.resource_id
#   scalable_dimension     = aws_appautoscaling_target.ecs_target.scalable_dimension
#   policy_type            = "TargetTrackingScaling"

#   target_tracking_scaling_policy_configuration {
#     target_value       = 75.0
#     predefined_metric_specification {
#       predefined_metric_type = "ECSServiceAverageCPUUtilization"
#     }
#     scale_out_cooldown  = 60
#     scale_in_cooldown   = 60
#   }
# }

# # Security Group for ECS - only allows outbound traffic for background processing
# resource "aws_security_group" "ecs_sg" {
#   name   = "${var.APP_IDENT}-ecs-sg"
#   vpc_id = data.aws_vpc.selected.id

#   # Allow all outbound traffic for API calls, database connections, etc.
#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
# }

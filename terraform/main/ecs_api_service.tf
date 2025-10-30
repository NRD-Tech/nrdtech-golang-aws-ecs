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
#       weight            = 2
#     },
#     {
#       capacity_provider = "FARGATE_SPOT"
#       weight            = 8
#     }
#   ])

#   ec2_strategy = tolist([
#     {
#       capacity_provider = "EC2"
#       weight            = 1
#     }
#   ])

#   # 2. Define your local “ecs_target” by picking one of the above
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

# # ECS Service
# resource "aws_ecs_service" "ecs_service" {
#   name            = "${var.APP_IDENT}-service"
#   cluster         = aws_ecs_cluster.ecs.arn
#   task_definition = aws_ecs_task_definition.task_definition.arn
#   desired_count   = var.MIN_COUNT
#   deployment_maximum_percent         = 200
#   deployment_minimum_healthy_percent = 100

#   # Add tags to ensure ECS tasks inherit the awsApplication tag for cost tracking
#   tags = data.terraform_remote_state.app_bootstrap.outputs.app_tags

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

#   load_balancer {
#     target_group_arn = aws_lb_target_group.ecs_target_group.arn
#     container_name   = var.APP_IDENT
#     container_port   = 8080
#   }

#   deployment_controller {
#     type = "ECS"
#   }

#   lifecycle {
#     create_before_destroy = true
#     ignore_changes        = [desired_count]
#   }
# }

# resource "aws_appautoscaling_target" "ecs_target" {
#   max_capacity       = var.MAX_COUNT
#   min_capacity       = var.MIN_COUNT
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

# # Application Load Balancer
# resource "aws_lb" "ecs_alb" {
#   name               = "${var.APP_IDENT}-alb"
#   internal           = false
#   load_balancer_type = "application"
#   security_groups    = [aws_security_group.alb_sg.id]
#   subnets            = data.aws_subnets.public.ids
  
#   # Performance optimizations
#   enable_deletion_protection = false
#   enable_http2               = true
#   idle_timeout               = 60
# }

# # Target Group
# resource "aws_lb_target_group" "ecs_target_group" {
#   # NOTE: name cannot be longer than 32 characters
#   name        = "${var.APP_IDENT}-tg"
#   port        = 8080
#   protocol    = "HTTP"
#   vpc_id      = data.aws_vpc.selected.id
#   target_type = "ip" # Change this from "instance" to "ip"
  
#   # Performance optimizations
#   deregistration_delay = 30  # Faster instance removal
  
#   health_check {
#     path                = "/healthcheck"
#     healthy_threshold   = 2
#     unhealthy_threshold = 2
#     timeout             = 5
#     interval            = 10
#     matcher             = "200"
#     port                = "traffic-port"
#     protocol            = "HTTP"
#   }
# }

# # Listener for ALB
# resource "aws_lb_listener" "http_listener" {
#   load_balancer_arn = aws_lb.ecs_alb.arn
#   port              = 80
#   protocol          = "HTTP"

#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.ecs_target_group.arn
#   }
# }

# resource "aws_lb_listener" "https_listener" {
#   depends_on = [aws_acm_certificate_validation.cert_validation]
#   load_balancer_arn = aws_lb.ecs_alb.arn
#   port              = 443
#   protocol          = "HTTPS"
#   ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06" # Supports TLS 1.3 for better performance
#   certificate_arn   = aws_acm_certificate.cert.arn

#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.ecs_target_group.arn
#   }
# }

# # Security Group for ECS and ALB
# resource "aws_security_group" "ecs_sg" {
#   name   = "${var.APP_IDENT}-ecs-sg"
#   vpc_id = data.aws_vpc.selected.id

#   ingress {
#     from_port   = 8080
#     to_port     = 8080
#     protocol    = "tcp"
#     cidr_blocks = ["0.0.0.0/0"]
#   }

#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
# }

# resource "aws_security_group" "alb_sg" {
#   name   = "${var.APP_IDENT}-alb-sg"
#   vpc_id = data.aws_vpc.selected.id

#   ingress {
#     from_port   = 80
#     to_port     = 80
#     protocol    = "tcp"
#     cidr_blocks = ["0.0.0.0/0"]
#   }

#   ingress {
#     from_port   = 443
#     to_port     = 443
#     protocol    = "tcp"
#     cidr_blocks = ["0.0.0.0/0"]
#   }

#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
# }

# ############## route53

# resource "aws_route53_record" "alb_dns_record" {
#   zone_id = data.aws_route53_zone.api_domain.zone_id
#   name    = var.API_DOMAIN
#   type    = "A"

#   alias {
#     name                   = aws_lb.ecs_alb.dns_name
#     zone_id                = aws_lb.ecs_alb.zone_id
#     evaluate_target_health = true
#   }
# }

# ############## cert

# resource "aws_acm_certificate" "cert" {
#   domain_name       = var.API_DOMAIN
#   validation_method = "DNS"

#   tags = {
#     Environment = "test"
#   }

#   lifecycle {
#     create_before_destroy = true
#   }
# }

# resource "aws_acm_certificate_validation" "cert_validation" {
#   certificate_arn         = aws_acm_certificate.cert.arn
#   validation_record_fqdns = [for record in aws_route53_record.cert_validation_records : record.fqdn]

#   depends_on = [aws_route53_record.cert_validation_records]
# }

# resource "aws_route53_record" "cert_validation_records" {
#   provider = aws.useast1
#   for_each = {
#     for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => {
#       name   = dvo.resource_record_name
#       record = dvo.resource_record_value
#       type   = dvo.resource_record_type
#     }
#   }

#   zone_id = data.aws_route53_zone.api_domain.zone_id
#   name    = each.value.name
#   type    = each.value.type
#   records = [each.value.record]
#   ttl     = 60
# }

# data "aws_route53_zone" "api_domain" {
#   name = "${var.API_ROOT_DOMAIN}."
# }

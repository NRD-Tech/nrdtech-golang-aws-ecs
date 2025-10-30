resource "aws_ecs_task_definition" "task_definition" {
  depends_on = [aws_cloudwatch_log_group.log_group, null_resource.push_image]
  family                   = var.APP_IDENT
  network_mode             = "awsvpc"
  requires_compatibilities = [var.LAUNCH_TYPE == "FARGATE_SPOT" ? "FARGATE" : var.LAUNCH_TYPE]
  cpu                      = var.APP_CPU
  memory                   = var.APP_MEMORY
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  # Add tags to ensure ECS tasks inherit the awsApplication tag for cost tracking
  tags = data.terraform_remote_state.app_bootstrap.outputs.app_tags

  runtime_platform {
    # Options: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#runtime-platform
    # Typical Options: LINUX, WINDOWS_SERVER_2022_FULL, WINDOWS_SERVER_2022_CORE, WINDOWS_SERVER_2019_FULL, WINDOWS_SERVER_2019_CORE
    operating_system_family = "LINUX"

    # Options: X86_64, ARM64
    cpu_architecture        = var.CPU_ARCHITECTURE
  }

  container_definitions = jsonencode([{
    name      = var.APP_IDENT
    image     = "${aws_ecr_repository.ecr_repository.repository_url}:${null_resource.push_image.triggers.code_hash}"
    cpu       = var.APP_CPU
    memory    = var.APP_MEMORY
    
    # Performance optimizations
    essential = true
    stopTimeout = 30
    
    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]
          logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.log_group.name
          awslogs-region        = var.AWS_REGION
          awslogs-stream-prefix = "ecs"
        }
      }
      environment = [
          {
            name = "ENVIRONMENT"
            value = var.ENVIRONMENT
          },
          {
            name  = "AWS_REGION"
            value = var.AWS_REGION
          }
      ]
  }])
}

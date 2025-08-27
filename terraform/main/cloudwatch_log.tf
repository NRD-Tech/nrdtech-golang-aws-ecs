resource "aws_cloudwatch_log_group" "log_group" {
  name = "/ecs/${var.APP_IDENT}"
}

# Enable enhanced Container Insights for the ECS cluster
resource "aws_cloudwatch_log_group" "container_insights" {
  name = "/aws/ecs/containerinsights/${var.APP_IDENT}/performance"
}

# IAM policy for Container Insights
resource "aws_iam_policy" "container_insights" {
  name = "${var.APP_IDENT}-container-insights-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ecs:ListClusters",
          "ecs:ListContainerInstances",
          "ecs:DescribeContainerInstances"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          aws_cloudwatch_log_group.container_insights.arn,
          "${aws_cloudwatch_log_group.container_insights.arn}:*"
        ]
      }
    ]
  })
}

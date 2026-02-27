# API base URL for testing (only when trigger_type = ecs_api_service)
output "api_base_url" {
  description = "Base URL for the API: HTTPS if API_DOMAIN is set, else HTTP ALB DNS."
  value       = local.ecs_api_service_enabled ? (var.API_DOMAIN != "" ? "https://${var.API_DOMAIN}" : "http://${aws_lb.ecs_alb[0].dns_name}") : null
}

output "api_healthcheck_url" {
  description = "Healthcheck endpoint URL (ALB uses this; call to verify the API is up)."
  value       = local.ecs_api_service_enabled ? (var.API_DOMAIN != "" ? "https://${var.API_DOMAIN}/healthcheck" : "http://${aws_lb.ecs_alb[0].dns_name}/healthcheck") : null
}

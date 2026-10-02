output "backend_ecr_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "worker_ecr_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "frontend_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

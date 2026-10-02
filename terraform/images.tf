# Resolve tags to digests so Terraform detects new images.
data "aws_ecr_image" "backend" {
  repository_name = aws_ecr_repository.backend.name
  image_tag       = var.backend_image_tag
}

data "aws_ecr_image" "worker" {
  repository_name = aws_ecr_repository.worker.name
  image_tag       = var.worker_image_tag
}

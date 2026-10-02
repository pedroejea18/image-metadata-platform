variable "project_name" {
  default = "image-metadata-project"
}

variable "images_bucket_name" {
  description = "Globally unique S3 bucket name for originals and thumbnails."
  type        = string
  default     = "images-metadata-files"
}

variable "frontend_bucket_name" {
  description = "Globally unique S3 bucket name for the shared frontend."
  type        = string
  default     = "front-image-metadata"
}

variable "backend_image_tag" {
  description = "ECR tag of the backend image to deploy."
  type        = string
  default     = "latest"
}

variable "worker_image_tag" {
  description = "ECR tag of the Lambda worker image to deploy."
  type        = string
  default     = "latest"
}

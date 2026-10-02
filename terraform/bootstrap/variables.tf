variable "state_bucket_name" {
  description = "Globally unique S3 bucket name for the root Terraform state."
  type        = string
  default     = "image-metadata-bucket-pedro"
}

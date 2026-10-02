module "s3-bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "5.16.0"

  bucket = var.state_bucket_name

  versioning = {
    enabled = true
  }

}

# Store originals and thumbnails in this bucket.
module "s3-bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "5.16.1"

  bucket = var.images_bucket_name
  acl    = "private"

  control_object_ownership = true
  object_ownership         = "ObjectWriter"

  versioning = {
    enabled = true
  }
}

# CloudFront serves files from this private bucket.
resource "aws_s3_bucket" "frontend" {
  bucket = var.frontend_bucket_name
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# Publish the shared frontend files.
resource "aws_s3_object" "index" {
  bucket = aws_s3_bucket.frontend.id
  key    = "index.html"

  source       = "${path.module}/../frontend/index.html"
  content_type = "text/html"

  etag = filemd5("${path.module}/../frontend/index.html")
}

resource "aws_s3_object" "css" {
  bucket = aws_s3_bucket.frontend.id
  key    = "styles.css"

  source       = "${path.module}/../frontend/styles.css"
  content_type = "text/css"

  etag = filemd5("${path.module}/../frontend/styles.css")
}

resource "aws_s3_object" "js" {
  bucket = aws_s3_bucket.frontend.id
  key    = "app.js"

  source       = "${path.module}/../frontend/app.js"
  content_type = "application/javascript"

  etag = filemd5("${path.module}/../frontend/app.js")
}

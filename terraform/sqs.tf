module "sqs" {
  source  = "terraform-aws-modules/sqs/aws"
  version = "5.2.2"

  name = "image-metadata-sqs"

  fifo_queue = false

  # Give Lambda retries six times the function timeout.
  visibility_timeout_seconds = 360

  tags = {
    Environment = "dev"
  }
}

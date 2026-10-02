resource "random_password" "postgres" {
  length           = 32
  special          = true
  override_special = "!#$%&*+-=?^_"
}

module "secrets_manager" {
  source  = "terraform-aws-modules/secrets-manager/aws"
  version = "2.1.1"

  name_prefix = "image-metadata-db-password-"
  description = "Password for the image metadata PostgreSQL database"

  recovery_window_in_days = 7

  secret_string = random_password.postgres.result

  tags = {
    Environment = "dev"
    Project     = var.project_name
  }
}

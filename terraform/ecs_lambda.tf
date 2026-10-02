resource "aws_ecr_repository" "worker" {
  name = "image-metadata-worker"

  tags = {
    Environment = "dev"
    Project     = var.project_name
  }
}

resource "aws_iam_role" "lambda_worker" {
  name = "image-metadata-lambda-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

data "aws_iam_policy_document" "lambda_worker" {

  statement {
    effect = "Allow"

    actions = [
      "s3:GetObject"
    ]

    resources = [
      "${module.s3-bucket.s3_bucket_arn}/originals/*"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "s3:PutObject"
    ]

    resources = [
      "${module.s3-bucket.s3_bucket_arn}/thumbnails/*"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue"
    ]

    resources = [
      module.secrets_manager.secret_arn
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]

    resources = [
      module.sqs.queue_arn
    ]
  }
}

resource "aws_iam_policy" "lambda_worker" {
  name   = "image-metadata-lambda-worker-policy"
  policy = data.aws_iam_policy_document.lambda_worker.json
}

resource "aws_iam_role_policy_attachment" "lambda_worker" {
  role       = aws_iam_role.lambda_worker.name
  policy_arn = aws_iam_policy.lambda_worker.arn
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role = aws_iam_role.lambda_worker.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Allow Lambda to create network interfaces for VPC access.
resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role = aws_iam_role.lambda_worker.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_security_group" "lambda" {
  name        = "image-metadata-lambda-sg"
  description = "Security group for image metadata worker Lambda"
  vpc_id      = aws_vpc.vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = "dev"
    Project     = var.project_name
  }
}

resource "aws_lambda_function" "worker" {
  function_name = "image-metadata-worker"

  package_type = "Image"

  image_uri = data.aws_ecr_image.worker.image_uri

  role = aws_iam_role.lambda_worker.arn

  timeout     = 60
  memory_size = 512

  environment {
    variables = {
      APP_ENV       = "aws"
      POSTGRES_HOST = aws_db_instance.postgres.address
      POSTGRES_PORT = tostring(aws_db_instance.postgres.port)
      POSTGRES_DB   = aws_db_instance.postgres.db_name
      POSTGRES_USER = aws_db_instance.postgres.username

      S3_BUCKET_IMAGES = module.s3-bucket.s3_bucket_id

      SECRET_ARN = module.secrets_manager.secret_arn
    }
  }

  vpc_config {
    subnet_ids = [
      for subnet in values(aws_subnet.private_subnets) : subnet.id
    ]

    security_group_ids = [
      aws_security_group.lambda.id
    ]
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_vpc_access,
    aws_iam_role_policy_attachment.lambda_worker
  ]

  tags = {
    Environment = "dev"
    Project     = var.project_name
  }
}

# Invoke the worker when messages are available in SQS.
resource "aws_lambda_event_source_mapping" "sqs_worker" {
  event_source_arn = module.sqs.queue_arn
  function_name    = aws_lambda_function.worker.arn

  batch_size = 10

  enabled = true
}

# Allow private subnets to reach S3.
resource "aws_vpc_endpoint" "s3" {
  vpc_id = aws_vpc.vpc.id

  service_name = "com.amazonaws.us-east-1.s3"

  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    aws_route_table.private.id
  ]

  tags = {
    Name = "image-metadata-s3-endpoint"
  }
}

# Allow ECS and Lambda to reach Secrets Manager over HTTPS.
resource "aws_security_group" "secrets_endpoint" {
  name   = "secrets-manager-endpoint-sg"
  vpc_id = aws_vpc.vpc.id

  ingress {
    from_port = 443
    to_port   = 443
    protocol  = "tcp"

    security_groups = [
      aws_security_group.lambda.id,
      aws_security_group.ecs-sg.id
    ]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "secrets-manager-endpoint-sg"
  }
}

resource "aws_vpc_endpoint" "secrets_manager" {
  vpc_id = aws_vpc.vpc.id

  service_name = "com.amazonaws.us-east-1.secretsmanager"

  vpc_endpoint_type = "Interface"

  subnet_ids = [
    for subnet in values(aws_subnet.private_subnets) : subnet.id
  ]

  security_group_ids = [
    aws_security_group.secrets_endpoint.id
  ]

  private_dns_enabled = true

  tags = {
    Name = "image-metadata-secrets-manager-endpoint"
  }
}

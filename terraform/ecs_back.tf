resource "aws_ecr_repository" "backend" {
  name = "image-metadata-backend"
}

resource "aws_ecs_cluster" "main" {
  name = "image-metadata"
}

# ECS uses this role to pull images and read the database secret.
resource "aws_iam_role" "ecs_execution" {
  name = "image-metadata-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_default" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "ecs_execution_secrets" {
  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue"
    ]

    resources = [
      module.secrets_manager.secret_arn
    ]
  }
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "image-metadata-ecs-secrets"

  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_execution_secrets.json
}

# The backend uses this role to access S3 and SQS.
resource "aws_iam_role" "ecs_task" {
  name = "image-metadata-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

data "aws_iam_policy_document" "ecs_task" {

  statement {
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:GetObject"
    ]

    resources = [
      "${module.s3-bucket.s3_bucket_arn}/originals/*"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "s3:GetObject"
    ]

    resources = [
      "${module.s3-bucket.s3_bucket_arn}/thumbnails/*"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "sqs:SendMessage"
    ]

    resources = [
      module.sqs.queue_arn
    ]
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "image-metadata-backend"

  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task.json
}

# Allow backend traffic only from the ALB.
resource "aws_security_group" "ecs-sg" {
  name   = "ecs-sg-image"
  vpc_id = aws_vpc.vpc.id

  ingress {
    from_port = 8000
    to_port   = 8000
    protocol  = "tcp"

    security_groups = [
      aws_security_group.alb-sg.id
    ]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "backend" {
  family = "image-metadata-backend"

  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = 256
  memory = 512

  execution_role_arn = aws_iam_role.ecs_execution.arn

  task_role_arn = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = data.aws_ecr_image.backend.image_uri
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "APP_ENV"
          value = "aws"
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = "us-east-1"
        },
        {
          name  = "POSTGRES_HOST"
          value = aws_db_instance.postgres.address
        },
        {
          name  = "POSTGRES_PORT"
          value = tostring(aws_db_instance.postgres.port)
        },
        {
          name  = "POSTGRES_DB"
          value = aws_db_instance.postgres.db_name
        },
        {
          name  = "POSTGRES_USER"
          value = aws_db_instance.postgres.username
        },
        {
          name  = "S3_BUCKET_IMAGES"
          value = module.s3-bucket.s3_bucket_id
        },
        {
          name  = "SQS_QUEUE_URL"
          value = module.sqs.queue_url
        }
      ]

      secrets = [
        {
          name      = "POSTGRES_PASSWORD"
          valueFrom = module.secrets_manager.secret_arn
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "backend" {
  name    = "backend"
  cluster = aws_ecs_cluster.main.id

  task_definition = aws_ecs_task_definition.backend.arn

  desired_count = 1
  launch_type   = "FARGATE"

  network_configuration {

    subnets = [
      for subnet in values(aws_subnet.public_subnets) : subnet.id
    ]

    security_groups = [
      aws_security_group.ecs-sg.id
    ]

    # Public IPs provide outbound access without a NAT gateway.
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.back_tg.arn

    container_name = "backend"
    container_port = 8000
  }
}

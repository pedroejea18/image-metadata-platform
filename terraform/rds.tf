# Place the database in private subnets.
resource "aws_db_subnet_group" "postgres" {
  name = "image-metadata-db-subnets"

  subnet_ids = [for subnet in values(aws_subnet.private_subnets) : subnet.id]

  tags = {
    Name = "image-metadata-db-subnets"
  }
}

# Allow database connections from the backend and worker.
resource "aws_security_group" "rds" {
  name   = "image-metadata-db-sg"
  vpc_id = aws_vpc.vpc.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs-sg.id, aws_security_group.lambda.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier = "image-metadata-db"

  engine = "postgres"

  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = "image_metadata"
  username = "postgres"
  password = random_password.postgres.result

  port = 5432

  db_subnet_group_name = aws_db_subnet_group.postgres.name

  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible = false

  multi_az = false

  skip_final_snapshot = true

  tags = {
    Environment = "dev"
  }
}

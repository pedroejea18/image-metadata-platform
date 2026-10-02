resource "aws_alb" "alb" {
  name               = "alb-image"
  internal           = false
  load_balancer_type = "application"

  security_groups = [
    aws_security_group.alb-sg.id
  ]

  subnets = [
    for subnet in values(aws_subnet.public_subnets) : subnet.id
  ]

  tags = {
    Name = var.project_name
  }
}

resource "aws_lb_target_group" "back_tg" {
  name        = "back-tg-alb"
  target_type = "ip"

  port     = 8000
  protocol = "HTTP"

  vpc_id = aws_vpc.vpc.id

  health_check {
    path     = "/"
    protocol = "HTTP"
  }
}

resource "aws_lb_listener" "back_listener" {
  load_balancer_arn = aws_alb.alb.arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.back_tg.arn
  }
}

resource "aws_security_group" "alb-sg" {
  name   = "alb-sg-image"
  vpc_id = aws_vpc.vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
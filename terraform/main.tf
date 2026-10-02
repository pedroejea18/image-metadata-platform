locals {
  public_subnets_cidr_block = {
    "us-east-1a" : "10.0.1.0/24",
    "us-east-1b" : "10.0.16.0/24",
  }
  private_subnets_cidr_block = {
    "us-east-1a" : "10.0.25.0/24",
    "us-east-1b" : "10.0.32.0/24",
  }
}

resource "aws_vpc" "vpc" {
  cidr_block = "10.0.0.0/16"

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    name        = var.project_name
    environment = "dev"
  }
}

resource "aws_subnet" "public_subnets" {
  for_each          = local.public_subnets_cidr_block
  vpc_id            = aws_vpc.vpc.id
  availability_zone = each.key
  cidr_block        = each.value

  tags = {
    name = "public-subnet"
  }
}

resource "aws_subnet" "private_subnets" {
  for_each          = local.private_subnets_cidr_block
  vpc_id            = aws_vpc.vpc.id
  availability_zone = each.key
  cidr_block        = each.value

  tags = {
    name = "private-subnet"
  }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    name = var.project_name
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "public-route-table"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "private-route-table"
  }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.gw.id
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private_subnets

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "route_table_asso_1" {
  for_each       = aws_subnet.public_subnets
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

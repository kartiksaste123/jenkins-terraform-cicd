# ---------------------------------------------------------------
# Data sources: latest Amazon Linux 2023 AMI and the default VPC
# ---------------------------------------------------------------
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

locals {
  name = "${var.project_name}-${var.environment}"

  # Boot script: install Docker + git, clone the repo, build and run the app on port 80
  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail
    dnf install -y docker git
    systemctl enable --now docker
    git clone --depth 1 --branch ${var.app_branch} ${var.app_repo_url} /opt/app
    cd /opt/app
    docker build --build-arg BUILD_NUMBER=ec2 -t student-task-tracker:latest .
    docker run -d --name student-task-tracker --restart unless-stopped \
      -p 80:5000 -p 5000:5000 -e APP_VERSION=1.0.0 student-task-tracker:latest
  EOT
}

# ---------------------------------------------------------------
# Security group: SSH from a restricted CIDR, HTTP 80/5000 public
# ---------------------------------------------------------------
resource "aws_security_group" "app" {
  name        = "${local.name}-sg"
  description = "Allow SSH from admin CIDR and HTTP/Flask from anywhere"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Flask app port"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name}-sg"
  }
}

# ---------------------------------------------------------------
# EC2 instance running the Student Task Tracker app
# ---------------------------------------------------------------
resource "aws_instance" "app" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.app.id]
  key_name                    = var.key_name
  associate_public_ip_address = true
  user_data                   = local.user_data
  user_data_replace_on_change = true

  # Require IMDSv2 (token-based instance metadata) for security
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "${local.name}-app"
  }
}

variable "aws_region" {
  description = "AWS region to deploy into (Mumbai by default)."
  type        = string
  default     = "ap-south-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must look like an AWS region code, e.g. ap-south-1."
  }
}

variable "project_name" {
  description = "Name prefix used for all resources."
  type        = string
  default     = "jenkins-terraform-cicd"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,32}$", var.project_name))
    error_message = "project_name must be 3-32 chars of lowercase letters, digits or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be one of dev, test or prod."
  }
}

variable "owner" {
  description = "Owner tag value."
  type        = string
  default     = "Kartik Saste"
}

variable "instance_type" {
  description = "EC2 instance type (free-tier eligible types only)."
  type        = string
  default     = "t3.micro"

  validation {
    condition     = contains(["t2.micro", "t3.micro"], var.instance_type)
    error_message = "Only free-tier eligible t2.micro or t3.micro are allowed."
  }
}

variable "ssh_cidr" {
  description = "CIDR block allowed to SSH (port 22) into the instance."
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition     = can(cidrhost(var.ssh_cidr, 0))
    error_message = "ssh_cidr must be a valid IPv4 CIDR block, e.g. 203.0.113.10/32."
  }
}

variable "key_name" {
  description = "Optional existing EC2 key pair name for SSH. Leave null for no key pair."
  type        = string
  default     = null
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 8

  validation {
    condition     = var.root_volume_size >= 8 && var.root_volume_size <= 30
    error_message = "root_volume_size must be between 8 and 30 GiB (free tier limit)."
  }
}

variable "app_repo_url" {
  description = "Public GitHub repository the instance clones and runs on boot."
  type        = string
  default     = "https://github.com/kartiksaste123/jenkins-terraform-cicd.git"
}

variable "app_branch" {
  description = "Git branch of the application to deploy."
  type        = string
  default     = "main"
}

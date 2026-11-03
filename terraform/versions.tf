# Terraform and provider version constraints (pinned for reproducible builds)
terraform {
  required_version = ">= 1.5.0"

  # Local state. Jenkins passes -backend-config="path=..." so the state file
  # lives in JENKINS_HOME and survives workspace cleanup between builds.
  # (In a team setup this would be an S3 backend with DynamoDB locking.)
  backend "local" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

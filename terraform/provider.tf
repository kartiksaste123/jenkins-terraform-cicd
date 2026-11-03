# AWS provider. Credentials come from the environment
# (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY injected by Jenkins,
# or ~/.aws/credentials locally) - never hard-coded here.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = "Terraform"
      Pipeline    = "Jenkins"
    }
  }
}

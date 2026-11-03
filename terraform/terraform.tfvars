aws_region       = "ap-south-1"
project_name     = "jenkins-terraform-cicd"
environment      = "dev"
owner            = "Kartik Saste"
instance_type    = "t3.micro"
ssh_cidr         = "100.22.120.45/32" # admin/Jenkins host public IP only
root_volume_size = 8
app_branch       = "main"

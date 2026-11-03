output "instance_id" {
  description = "ID of the EC2 instance."
  value       = aws_instance.app.id
}

output "ami_id" {
  description = "Amazon Linux 2023 AMI used."
  value       = data.aws_ami.amazon_linux_2023.id
}

output "public_ip" {
  description = "Public IPv4 address of the instance."
  value       = aws_instance.app.public_ip
}

output "public_dns" {
  description = "Public DNS name of the instance."
  value       = aws_instance.app.public_dns
}

output "security_group_id" {
  description = "ID of the application security group."
  value       = aws_security_group.app.id
}

output "app_url" {
  description = "URL of the Student Task Tracker app on EC2."
  value       = "http://${aws_instance.app.public_ip}/"
}

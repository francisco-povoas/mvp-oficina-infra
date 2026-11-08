variable "aws_region" {
  description = "AWS region expected by the future platform root."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment; it is independent from Git branches."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "eks_node_instance_types" {
  description = "Approved initial EKS node types."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "eks_node_desired_size" {
  description = "Approved initial worker count."
  type        = number
  default     = 2

  validation {
    condition     = var.eks_node_desired_size >= 2
    error_message = "The approved initial target requires at least two nodes."
  }
}

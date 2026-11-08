locals {
  business_services = toset([
    "mvp-oficina-ordens",
    "mvp-oficina-recursos",
    "mvp-oficina-financeiro",
  ])

  approved_target = {
    kubernetes = {
      service = "EKS"
      nodes   = var.eks_node_desired_size
      types   = var.eks_node_instance_types
    }
    postgres = {
      service           = "RDS PostgreSQL"
      logical_databases = ["ordens", "recursos"]
      independent_users = true
      publicly_exposed  = false
    }
    financeiro = {
      service = "DynamoDB"
      indexes = ["GSI1", "GSI2"]
    }
    messaging = {
      service = "SQS FIFO"
      dlq     = true
    }
    registries = {
      service      = "ECR"
      repositories = local.business_services
      immutable    = true
    }
  }
}

check "approved_node_shape" {
  assert {
    condition = (
      var.eks_node_desired_size == 2 &&
      var.eks_node_instance_types == ["t3.medium"]
    )
    error_message = "The Stage 4 baseline is exactly two t3.medium nodes; change only with a recorded decision."
  }
}

check "three_independent_services" {
  assert {
    condition     = length(local.business_services) == 3
    error_message = "The platform contract must retain exactly the three approved business services."
  }
}

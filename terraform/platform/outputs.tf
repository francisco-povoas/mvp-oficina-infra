output "platform_contract" {
  description = "Non-provisioning contract consumed while implementing Stage 4."
  value       = local.approved_target
}

output "implementation_status" {
  description = "Prevents this skeleton from being mistaken for provisionable infrastructure."
  value       = "prepared-not-implemented-stage-1"
}

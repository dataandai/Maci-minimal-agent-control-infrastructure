resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-users"

  auto_verified_attributes = ["email"]

  mfa_configuration = var.mfa_configuration

  dynamic "software_token_mfa_configuration" {
    for_each = var.mfa_configuration == "OFF" ? [] : [1]
    content {
      enabled = true
    }
  }

  user_pool_add_ons {
    advanced_security_mode = var.advanced_security_mode
  }

  schema {
    name                = "tenant_id"
    attribute_data_type = "String"
    mutable             = true
    required            = false

    string_attribute_constraints {
      min_length = "1"
      max_length = "128"
    }
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "this" {
  name         = "${var.name_prefix}-client"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  # SRP keeps the password off the wire. ADMIN_USER_PASSWORD_AUTH is retained
  # only for the admin-initiated dev token helper. Plain USER_PASSWORD_AUTH is
  # intentionally removed so credentials are never sent directly by clients.
  explicit_auth_flows = [
    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  read_attributes  = ["email", "custom:tenant_id"]
  write_attributes = ["email", "custom:tenant_id"]

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from botocore.exceptions import ClientError  # type: ignore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or update a Cognito demo user with a custom tenant_id claim."
    )
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--password", required=False, help="Permanent demo password")
    parser.add_argument(
        "--temporary-password",
        required=False,
        help="Backward-compatible alias for --password. The script sets it as a permanent password.",
    )
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    password = args.password or args.temporary_password
    if not password:
        raise SystemExit("Provide --password or --temporary-password")

    import boto3  # type: ignore

    client = boto3.client("cognito-idp", region_name=args.region)
    attributes = [
        {"Name": "email", "Value": args.email},
        {"Name": "email_verified", "Value": "true"},
        {"Name": "custom:tenant_id", "Value": args.tenant_id},
    ]

    try:
        client.admin_create_user(
            UserPoolId=args.user_pool_id,
            Username=args.username,
            TemporaryPassword=password,
            MessageAction="SUPPRESS",
            UserAttributes=attributes,
        )
        print(f"created demo user {args.username}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code != "UsernameExistsException":
            raise
        print(f"demo user {args.username} already exists; updating attributes/password")
        client.admin_update_user_attributes(
            UserPoolId=args.user_pool_id,
            Username=args.username,
            UserAttributes=attributes,
        )

    client.admin_set_user_password(
        UserPoolId=args.user_pool_id,
        Username=args.username,
        Password=password,
        Permanent=True,
    )
    print(f"demo user {args.username} is ready for tenant {args.tenant_id}")


if __name__ == "__main__":
    main()

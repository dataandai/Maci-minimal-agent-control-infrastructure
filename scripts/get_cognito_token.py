#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Get a Cognito ID token for local smoke tests.")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    import boto3  # type: ignore

    client = boto3.client("cognito-idp", region_name=args.region)
    response = client.initiate_auth(
        ClientId=args.client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": args.username, "PASSWORD": args.password},
    )
    print(json.dumps(response["AuthenticationResult"], indent=2))


if __name__ == "__main__":
    main()

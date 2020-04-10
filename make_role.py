# pylint: disable=bare-except
import json
import os

import boto3
import tomlkit


def get_project_meta() -> dict:
    pyproj_path = "./pyproject.toml"
    if os.path.exists(pyproj_path):
        with open(pyproj_path, "r") as pyproject:
            file_contents = pyproject.read()
        return tomlkit.parse(file_contents)["tool"]["poetry"]
    else:
        return {}


account_id = boto3.client("sts").get_caller_identity().get("Account")
ssm_kms_key = os.getenv("SSM_KMS_KEY")
secrets_kms_key = os.getenv("SECRETS_KMS_KEY")
docker_secret_id = os.getenv("DOCKER_SECRET_ID")


pkg_meta = get_project_meta()
project = pkg_meta.get("name")
version = pkg_meta.get("version")

iam = boto3.client("iam")

path = "/"
role_name = f"{project}-role"
description = f"Task role for {project}"

trust_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

policy_name = f"{project}-policy"
policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["ssm:GetParameter*", "ssm:Describe*", "ssm:List*", "ssm:Get*"],
            "Resource": [
                f"arn:aws:ssm:*:*:parameter/{project}/*",
                "arn:aws:ssm:*:*:parameter/datadog/*",
            ],
        },
        {
            "Effect": "Allow",
            "Action": [
                "kms:ListKeys",
                "kms:ListAliases",
                "kms:Describe*",
                "kms:Decrypt",
            ],
            "Resource": f"arn:aws:kms:us-east-1:{account_id}:key/{ssm_kms_key}",
        },
        {
            "Effect": "Allow",
            "Action": ["kms:Decrypt", "secretsmanager:GetSecretValue"],
            "Resource": [
                f"arn:aws:secretsmanager:us-east-1:{account_id}:secret:{docker_secret_id}",
                f"arn:aws:kms:us-east-1:{account_id}:key/{secrets_kms_key}",
            ],
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:CreateNetworkInterface",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DetachNetworkInterface",
                "ec2:DeleteNetworkInterface",
            ],
            "Resource": "*",
        },
    ],
}

tags = [{"Key": "service_name", "Value": project}]


def delete_previous_policy_versions():
    versions = [
        x["VersionId"]
        for x in iam.list_policy_versions(PolicyArn=policy_arn)["Versions"]
    ]

    for v in versions:
        try:
            iam.delete_policy_version(PolicyArn=policy_arn, VersionId=v)
            print(f"Deleted old revision: {v}")
        except Exception:
            pass


try:
    role = iam.create_role(
        Path=path,
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description=description,
        MaxSessionDuration=3600,
        Tags=tags,
    )
    print(f"Created role: {role_name}")

except Exception:
    role = iam.get_role(RoleName=role_name)
    print(f"Retrieved role: {role_name}")


try:
    policy_response = iam.create_policy(
        PolicyName=policy_name, PolicyDocument=json.dumps(policy)
    )
    print(f"Created policy: {policy_name}")
except Exception:
    old_policy = iam.get_policy(PolicyArn=policy_arn)
    old_revnum = old_policy.get("Policy", {}).get("DefaultVersionId", "")

    policy_response = iam.create_policy_version(
        PolicyArn=policy_arn, PolicyDocument=json.dumps(policy)
    )
    revnum = policy_response.get("PolicyVersion", {}).get("VersionId", "")

    print(f"Created policy revision: {revnum}")

    default_response = iam.set_default_policy_version(
        PolicyArn=policy_arn, VersionId=revnum
    )
    print(f"Updated default policy version to {old_revnum} -> {revnum}")

    delete_previous_policy_versions()

iam.attach_role_policy(PolicyArn=policy_arn, RoleName=role_name)
print("Attached policy to role")

print("Success")

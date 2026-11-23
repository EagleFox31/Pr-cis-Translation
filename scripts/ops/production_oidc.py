"""One-time CloudShell migration of the two existing Précis OIDC trusts.

Default is a read-only plan. --apply changes only the environment in the exact
repository subject; it never changes role permissions, servers or application env.
"""
import argparse
from copy import deepcopy
import json
import subprocess

ACCOUNT = "458018461157"
ROLES = ("precis-translation-staging-github-deployer", "precis-translation-staging-free-plan-read")
PREFIXES = ("repo:EagleFox31@86088743/Pr-cis-Translation@1411758415:environment:",
            "repo:EagleFox31/Pr-cis-Translation:environment:")


def production_trust(document):
    result = deepcopy(document)
    statements = result.get("Statement", [])
    if not isinstance(statements, list) or len(statements) != 1:
        raise ValueError("Unexpected trust statements; review before migration")
    statement = statements[0]
    if (statement.get("Effect") != "Allow" or
        statement.get("Action") != "sts:AssumeRoleWithWebIdentity" or
        statement.get("Principal") != {"Federated": f"arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"}):
        raise ValueError("Unexpected OIDC principal or action")
    condition = statement.get("Condition", {})
    if set(condition) != {"StringEquals"}:
        raise ValueError("Unexpected trust condition")
    equals = condition["StringEquals"]
    if set(equals) != {"token.actions.githubusercontent.com:aud", "token.actions.githubusercontent.com:sub"} or equals["token.actions.githubusercontent.com:aud"] != "sts.amazonaws.com":
        raise ValueError("Unexpected OIDC audience or claims")
    subject = equals["token.actions.githubusercontent.com:sub"]
    subjects = [subject] if isinstance(subject, str) else subject
    allowed = {prefix + env for prefix in PREFIXES for env in ("staging", "production")}
    if not isinstance(subjects, list) or not subjects or any(value not in allowed for value in subjects):
        raise ValueError("Unexpected repository or environment; migration refused")
    migrated = sorted({value.rsplit(":", 1)[0] + ":production" for value in subjects})
    equals["token.actions.githubusercontent.com:sub"] = migrated[0] if len(migrated) == 1 else migrated
    return result


def aws(*args):
    value = subprocess.run(["aws", *args, "--region", "eu-west-3", "--output", "json"],
                           capture_output=True, text=True, check=True)
    return json.loads(value.stdout) if value.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if aws("sts", "get-caller-identity")["Account"] != ACCOUNT:
        raise SystemExit("Wrong AWS account; nothing changed")
    plans = []
    for role in ROLES:
        old = aws("iam", "get-role", "--role-name", role)["Role"]["AssumeRolePolicyDocument"]
        new = production_trust(old)
        plans.append((role, old, new))
    for role, old, new in plans:
        if args.apply and old != new:
            aws("iam", "update-assume-role-policy", "--role-name", role,
                "--policy-document", json.dumps(new))
        if args.apply:
            current = aws("iam", "get-role", "--role-name", role)["Role"]["AssumeRolePolicyDocument"]
            if production_trust(current) != current:
                raise SystemExit("Production OIDC verification failed")
        print(json.dumps({"role": role, "environment": "production", "applied": args.apply,
                          "change_required": old != new}))


if __name__ == "__main__":
    main()

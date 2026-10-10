#!/usr/bin/env python3
"""Strict CI check for the single tenant read-only CloudFormation IAM role.

CloudFormation validates final AWS semantics; this local test also rejects
duplicate YAML keys and accidental broad IAM policy in pull requests.
"""
from pathlib import Path
from collections.abc import Hashable

import yaml

PATH = Path("deploy/infra/aws-free-plan-readonly-role.yml")


class UniqueLoader(yaml.SafeLoader):
    pass


def read_unique_mapping(loader, node):
    pairs = loader.construct_pairs(node, deep=True)
    output = {}
    for key, value in pairs:
        if not isinstance(key, Hashable) or key in output:
            raise ValueError(f"Unhashable or duplicate YAML key: {key!r}")
        output[key] = value
    return output


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, read_unique_mapping)
for tag in ("!Ref", "!Sub", "!GetAtt"):
    UniqueLoader.add_constructor(tag, lambda loader, node: loader.construct_scalar(node))


def main():
    template = yaml.load(PATH.read_text(encoding="utf-8"), Loader=UniqueLoader)
    assert isinstance(template, dict), "CloudFormation template must be a mapping"
    assert template["AWSTemplateFormatVersion"] == "2010-09-09"
    resources = template["Resources"]
    assert set(resources) == {"PrecisStagingFreePlanReadRole"}, "Unexpected AWS resources"
    props = resources["PrecisStagingFreePlanReadRole"]["Properties"]
    assert resources["PrecisStagingFreePlanReadRole"]["Type"] == "AWS::IAM::Role"
    assert props["RoleName"] == "precis-translation-staging-free-plan-read"
    assert props["PermissionsBoundary"] == "PermissionsBoundaryArn"
    tags = {tag["Key"]: tag["Value"] for tag in props["Tags"]}
    assert tags == {"AppFactoryProject": "precis-translation", "AppFactoryEnvironment": "staging"}
    assert template["Parameters"]["GitHubOidcProviderArn"]["Type"] == "String"
    assert template["Parameters"]["PermissionsBoundaryArn"]["Type"] == "String"
    trusts = props["AssumeRolePolicyDocument"]["Statement"]
    assert len(trusts) == 1
    condition = trusts[0]["Condition"]["StringEquals"]
    assert condition["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert condition["token.actions.githubusercontent.com:sub"] == (
        "repo:EagleFox31@86088743/Pr-cis-Translation@1411758415:environment:staging"
    )
    policies = props["Policies"]
    assert len(policies) == 1
    statement = policies[0]["PolicyDocument"]["Statement"]
    assert statement == [{"Effect": "Allow", "Action": "freetier:GetAccountPlanState", "Resource": "*"}]
    assert template["Outputs"]["ReadOnlyRoleArn"]["Value"] == "PrecisStagingFreePlanReadRole.Arn"
    print("PASS: CloudFormation IAM YAML is well-formed, unique and read-only")


if __name__ == "__main__":
    main()

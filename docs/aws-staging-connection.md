# Précis Translation — AWS staging connection (no cloud resource launched)

## Status
The manual GitHub Actions workflow
`.github/workflows/aws-staging-credit-preflight.yml` calls the reviewed and
pinned reusable AppFactory Free Plan preflight at commit
`c71ac965a2c2b21590077486f11bf30a4c98b07f`.
The workflow is **read-only**: no EC2, no SSM SendCommand, no IAM mutations.

## One-time AWS connection required

1. In the AWS console, confirm you are in the intended account and **Free
   Plan** (not Paid), and check its credit balance and expiry date.
2. Confirm that IAM already has the GitHub Actions OpenID provider
   `token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.
   Do **not** create a duplicate provider. If absent, create one using AWS's
   GitHub OIDC setup guidance before proceeding.
3. The **public AppFactory bootstrap script** validates the AWS account and
   existing GitHub provider automatically. It is dry-run by default.
   After reviewing its narrowly scoped IAM-only template, the operator may
   explicitly apply it from AWS CloudShell (once per AWS trust setup).
   The existing `deploy/infra/aws-free-plan-readonly-role.yml` is retained as a
   separate project-specific reference template, not a second resource to deploy.
   Because this fork was created after July 15 2026, AppFactory pins immutable
   GitHub owner/repository IDs in the IAM role trust policy.
4. The role ARN is now a **reviewed constant** in the read-only GitHub workflow,
   so no repository variable is needed. This is an ARN, not a credential.
5. The GitHub `staging` environment should require reviewer approval; this
   must be configured by the repository administrator before real deployments.
6. Dispatch **AWS staging credit eligibility (read only; manual)** from
   `main`. It verifies real STS+Free Tier data, refuses Paid plans and
   requires at least USD 25 remaining and 14 days' validity.

If any of these prerequisites is absent, the job fails closed. Never paste
long-lived AWS access keys into a GitHub variable or into this repository.

## Deliberately out of scope
This preflight **does not** deploy Précis. Before launching an instance,
we still require a verified cost estimate covering EBS, IPv4 and network
traffic, explicit service availability under the Free Plan, an isolated
dedicated host, scoped SSM execution identity and backup/quiescence drill.
It must not use Atelier Maître's production instance or IAM role.

CloudShell bootstrap code lives in public AppFactory:
`scripts/deployment/bootstrap-aws-free-plan-reader.sh` with the reusable
`infra/aws/appfactory-free-plan-reader.yml` template. It refuses the wrong AWS
account. No GitHub or AWS secrets are stored in either repository.

The Free Plan can consume AWS promotional credits even though the operator
does not incur an invoice. The checks therefore refuse to continue near
credit exhaustion or account expiry.

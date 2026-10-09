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
3. The versioned template `deploy/infra/aws-free-plan-readonly-role.yml`
   declares a **separate read-only IAM role**, scoped to this fork's GitHub
   `staging` environment. It requires the existing OIDC provider ARN.
   Because this fork was created after 15 July 2026, its trust condition pins
   GitHub's **immutable owner/repository IDs** as well as the environment;
   the previous name-only `sub` form must not be used. Verify the exact
   OIDC subject against GitHub's repository OIDC settings if customized.
   This template is **not applied** automatically.
4. Review and explicitly deploy only this IAM template in the intended AWS
   account, using named-IAM-role acknowledgement. It grants only
   `freetier:GetAccountPlanState`; it cannot start servers or upgrade plans.
5. In `EagleFox31/Pr-cis-Translation`, configure GitHub environment
   `staging` with required reviewer approval. Add repository Actions
   variable `PRECIS_AWS_STAGING_READ_ROLE_ARN` with the role ARN returned
   by the IAM-only stack (this ARN is not a password).
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

The Free Plan can consume AWS promotional credits even though the operator
does not incur an invoice. The checks therefore refuse to continue near
credit exhaustion or account expiry.

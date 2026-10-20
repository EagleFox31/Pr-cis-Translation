# Précis production delivery

Précis already runs at https://precis-translator.trigenys.com. Its application
runtime is production and its EC2 lifecycle is persistent. GitHub and AppFactory
now use the explicit `production` environment; historical staging deployments
remain historical records.

The same EC2 instance, stack, role ARNs, SecureString and Compose volumes remain
in place. Their old `staging` substrings are resource identities, not another
environment to create. No new instance or secret reimport is needed.

AppFactory Project Automation manages the linked development Project through
the existing owner OAuth broker. AppFactory's reusable Release Please workflow
opens version PRs, updates the changelog/package version, tags and publishes
GitHub Releases. Release PRs run the existing CI, including when the default
GitHub token needs an explicit workflow-dispatch to start it. Publishing passes
the exact released SHA to the reusable production deployment workflow.

Existing AWS roles must trust this repository's production OIDC subject. Before
the first migrated deployment, an AWS administrator can run the reviewed
`scripts/ops/production_oidc.py --apply` from CloudShell. The script first checks
the AWS account and both existing role trusts, refuses unrelated/broad trust,
then changes only the environment suffix and verifies it. It never changes role
permissions, servers, billing or application secrets. Its default is read-only.

After that one-time migration, rerun failed production jobs. CI guards the
logical environment and release-to-deployment SHA mapping against regressions.

Initial release bootstrap is bounded to the existing deployed lineage at b022d2e689b241ffd1fb1db9e9a4cd8741bf7583. The first managed version is 1.2.0; later versions follow commits and the persisted manifest. This avoids scanning the unrelated initial repository history, which produced a GitHub GraphQL internal error during first adoption. Existing manual changelog entries are preserved.

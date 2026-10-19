# Source and production integration

The application update imports `09052783195bc3c5467858eabdb73a9e93fe2197`
from `EagleFox31/Precis-Translation`, forked from
`MbowouIbrah/Pr-cis-Translation`.

Production remains in `EagleFox31/Pr-cis-Translation` on its existing permanent
EC2 host. Its AppFactory AWS/SSM deployment workflow, SecureString parameter,
Compose project, persistent volumes, public origin, Caddy HTTPS and SEO
verification remain authoritative. The upstream alternative deploy/infra
workflows are not installed in this production repository.

Database revisions 0008 and 0009 add the persistent consumption ledger and
subscription/payment fields. CI rehearses the upgrade from revision 0007 with
existing users, credits, documents and payments. The host adapter builds first,
then saves and checks a private local PostgreSQL dump and document archive
before starting migrations. This is a local recovery copy, not an off-host
backup or proof of a production restoration.

Keep production database/JWT/provider credentials in the existing SSM parameter.
New optional settings (payment methods, DeepSeek balance thresholds and model
selection) have documented defaults in `backend/.env.example`. `ADMIN_EMAIL`
selects the account promoted by `seed_admin.py`; changing it requires the
intended account address. Deployments do not reset application data.

#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
readonly REF="$1"
[[ "$REF" =~ ^[a-f0-9]{40}$ ]] || exit 1
readonly REGION=eu-west-3
[[ "$(aws sts get-caller-identity --query Account --output text)" == 458018461157 ]] || { echo "Wrong AWS account"; exit 1; }
readonly HOST="$(aws cloudformation describe-stacks --region "$REGION" --stack-name precis-translation-staging-app --query "Stacks[0].Outputs[?OutputKey=='StagingInstanceId'].OutputValue | [0]" --output text)"
readonly SG="$(aws cloudformation describe-stacks --region "$REGION" --stack-name precis-translation-staging-app --query "Stacks[0].Outputs[?OutputKey=='StagingSecurityGroupId'].OutputValue | [0]" --output text)"
[[ "$HOST" =~ ^i-[a-f0-9]+$ && "$SG" =~ ^sg-[a-f0-9]+$ ]] || exit 1
readonly PROJECT="$(aws ec2 describe-instances --region "$REGION" --instance-ids "$HOST" --query "Reservations[0].Instances[0].Tags[?Key=='AppFactoryProject'].Value | [0]" --output text)"
[[ "$PROJECT" == precis-translation ]] || { echo "Wrong project"; exit 1; }
readonly TEMPLATE="$(mktemp /tmp/precis-public-network.XXXXXX.yml)"
trap 'rm -f "$TEMPLATE"' EXIT
curl -fsSL "https://raw.githubusercontent.com/EagleFox31/Pr-cis-Translation/$REF/deploy/infra/aws-public-network.yml" -o "$TEMPLATE"
aws cloudformation deploy --region "$REGION" --stack-name precis-translation-public-network \
  --template-file "$TEMPLATE" --parameter-overrides InstanceId="$HOST" SecurityGroupId="$SG" \
  --no-fail-on-empty-changeset
aws cloudformation describe-stacks --region "$REGION" --stack-name precis-translation-public-network \
  --query "Stacks[0].Outputs" --output table
echo "DNS: create A record, host precis, pointing to the PublicIp shown above."

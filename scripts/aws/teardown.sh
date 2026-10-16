#!/usr/bin/env bash
# Terminate every instance tagged project=cooloff. Pass --stop to only stop them.
set -euo pipefail
REGION=${AWS_REGION:-us-east-1}
ACTION=terminate; [ "${1:-}" = "--stop" ] && ACTION=stop
IDS=$(aws ec2 describe-instances --region "$REGION" --filters Name=tag:project,Values=cooloff Name=instance-state-name,Values=pending,running,stopped,stopping --query 'Reservations[].Instances[].InstanceId' --output text)
[ -z "$IDS" ] && { echo "nothing to do"; exit 0; }
echo "$ACTION: $IDS"
aws ec2 "$ACTION"-instances --region "$REGION" --instance-ids $IDS --query 'length(*[0])' --output text

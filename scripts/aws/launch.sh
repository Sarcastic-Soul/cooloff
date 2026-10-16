#!/usr/bin/env bash
# Launch a Decider test box on EC2. Usage: scripts/aws/launch.sh gpu|cpu
# No inbound ports. Reach the box with SSM:  aws ssm start-session --target <id>
# Needs: role/instance profile "cooloff-decider-ssm" (AmazonSSMManagedInstanceCore) and a security group with no inbound rules.
set -euo pipefail
MODE=${1:?usage: launch.sh gpu|cpu}
REGION=${AWS_REGION:-us-east-1}
SG=${COOLOFF_SG:?set COOLOFF_SG to the no-inbound security group id}
SUBNET=${COOLOFF_SUBNET:?set COOLOFF_SUBNET to a default-VPC subnet id}

case "$MODE" in
  gpu) TYPE=${COOLOFF_TYPE:-g6.xlarge}
       AMI=$(aws ssm get-parameter --region "$REGION" --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id --query Parameter.Value --output text) ;;
  cpu) TYPE=${COOLOFF_TYPE:-c7i.2xlarge}
       AMI=$(aws ssm get-parameter --region "$REGION" --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text) ;;
  *) echo "mode must be gpu or cpu" >&2; exit 2 ;;
esac

# Deep Learning AMIs already have docker and the NVIDIA toolkit. Plain Ubuntu needs docker installed.
VOLSIZE=80; [ "$MODE" = gpu ] && VOLSIZE=160   # the GPU deep learning image alone fills about 55 GB
USERDATA=$(mktemp)
cat > "$USERDATA" <<'UD'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
command -v docker >/dev/null || { apt-get update && apt-get install -y docker.io docker-compose-v2; systemctl enable --now docker; }
apt-get install -y git || true
usermod -aG docker ubuntu || true
touch /var/lib/cooloff-ready
UD

aws ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type "$TYPE" \
  --subnet-id "$SUBNET" --security-group-ids "$SG" \
  --iam-instance-profile Name=cooloff-decider-ssm \
  --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=${VOLSIZE},VolumeType=gp3,DeleteOnTermination=true}" \
  --metadata-options HttpTokens=required,HttpEndpoint=enabled \
  --user-data "file://$USERDATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=cooloff-decider-$MODE},{Key=project,Value=cooloff}]" 'ResourceType=volume,Tags=[{Key=project,Value=cooloff}]' \
  --query 'Instances[0].[InstanceId,InstanceType]' --output text
rm -f "$USERDATA"

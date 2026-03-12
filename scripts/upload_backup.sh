#!/usr/bin/env bash
set -euo pipefail

OPS_ENV="${OPS_ENV:-/etc/my-api/ops.env}"
BACKUP_FILE="${1:?backup file path is required}"

if [[ -r "$OPS_ENV" ]]; then
  set -a
  . "$OPS_ENV"
  set +a
fi

if [[ "${REMOTE_BACKUP_ENABLED:-false}" != "true" ]]; then
  exit 0
fi

: "${REMOTE_BACKUP_ENDPOINT:?REMOTE_BACKUP_ENDPOINT is required}"
: "${REMOTE_BACKUP_BUCKET:?REMOTE_BACKUP_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"

AWS_BIN_DEFAULT="$(command -v aws || true)"
AWS_BIN="${AWS_BIN:-$AWS_BIN_DEFAULT}"

if [[ -z "$AWS_BIN" ]]; then
  echo "aws CLI not found in PATH; set AWS_BIN or install aws" >&2
  exit 1
fi

remote_prefix="${REMOTE_BACKUP_PREFIX:-sqlite}"
remote_key="${remote_prefix%/}/$(basename "$BACKUP_FILE")"

"$AWS_BIN" --endpoint-url "$REMOTE_BACKUP_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://$REMOTE_BACKUP_BUCKET/$remote_key"

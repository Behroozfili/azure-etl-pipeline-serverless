#!/bin/bash
set -e

# Load environment variables from .env if it exists
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE"
    export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)
else
    echo "Warning: $ENV_FILE not found. Relying on pre-set environment variables."
fi

# Configuration
TRAIN_MODEL_QUEUE_NAME="${TRAIN_MODEL_QUEUE_NAME:-train-model-queue}"
QUEUE_MESSAGE_CONTENT='{"trigger_timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'", "source": "'$(basename "$0")'"}'

check_command() {
  if ! command -v "$1" &> /dev/null; then
    echo "Error: '$1' is not installed."
    exit 1
  fi
}

echo "---------------------------------------------------------------------"
echo "Triggering Model Training Process"
echo "---------------------------------------------------------------------"

check_command az

if [[ -z "$AZURE_STORAGE_ACCOUNT_NAME" ]]; then
  echo "Error: AZURE_STORAGE_ACCOUNT_NAME is not set."
  exit 1
fi

echo "Target Storage Account: $AZURE_STORAGE_ACCOUNT_NAME"
echo "Target Queue: $TRAIN_MODEL_QUEUE_NAME"
echo "Message Content: $QUEUE_MESSAGE_CONTENT"
echo ""

CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING:-}"

if [ -z "$CONNECTION_STRING" ]; then
  echo "No connection string found. Using Azure AD authentication (az login)."
else
  echo "Using connection string from environment."
fi

echo "Sending message to queue '$TRAIN_MODEL_QUEUE_NAME'..."

if [ -n "$CONNECTION_STRING" ]; then
  az storage message put \
    --queue-name "$TRAIN_MODEL_QUEUE_NAME" \
    --content "$QUEUE_MESSAGE_CONTENT" \
    --connection-string "$CONNECTION_STRING"
else
  az storage message put \
    --queue-name "$TRAIN_MODEL_QUEUE_NAME" \
    --content "$QUEUE_MESSAGE_CONTENT" \
    --account-name "$AZURE_STORAGE_ACCOUNT_NAME" \
    --auth-mode login
fi

if [ $? -eq 0 ]; then
  echo "---------------------------------------------------------------------"
  echo "Message sent successfully to queue '$TRAIN_MODEL_QUEUE_NAME'."
  echo "---------------------------------------------------------------------"
else
  echo "---------------------------------------------------------------------"
  echo "Error: Failed to send message to queue."
  echo "---------------------------------------------------------------------"
  exit 1
fi

exit 0

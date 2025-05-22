#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Optional: Print each command before executing it for debugging
# set -x

# ===================================================================================
# Load environment variables from .env file
# ===================================================================================
if [ -f .env ]; then
  echo "Loading environment variables from .env file..."
  export $(grep -v '^#' .env | sed 's/\r$//' | xargs -0 -d '\n' printf '%s\0' | xargs -0)
else
  echo "ERROR: .env file not found! Please ensure it exists and contains all necessary variables."
  exit 1
fi

# ===================================================================================
# Sanity check for required environment variables (based on .env and Bicep params)
# ===================================================================================
echo "Performing sanity check for required environment variables..."
required_vars=(
  "LOCATION"
  "RESOURCE_GROUP"
  "STORAGE_ACCOUNT_NAME" # Used for storage operations, not directly by Bicep if connection string is passed
  "FUNCTION_APP_NAME"
  "APPINSIGHTS_INSTRUMENTATIONKEY"
  "ACR_NAME"
  "DOCKER_REGISTRY_SERVER_USERNAME"
  "DOCKER_REGISTRY_SERVER_PASSWORD"
  "STORAGE_CONNECTION_STRING"
  "DATASETS_CONTAINER_NAME"
  "RAW_DATA_CONTAINER_NAME"
  "TRANSFORM_QUEUE_NAME"
  "FUNCTIONS_WORKER_RUNTIME"
  "WEBSITES_ENABLE_APP_SERVICE_STORAGE"
)
missing_vars=0
for var_name in "${required_vars[@]}"; do
  if [ -z "${!var_name}" ]; then
    echo "ERROR: Environment variable $var_name is not set. Please check your .env file."
    missing_vars=$((missing_vars + 1))
  fi
done

if [ "$missing_vars" -gt 0 ]; then
  echo "ERROR: $missing_vars required environment variable(s) are missing. Exiting."
  exit 1
fi
echo "Sanity check passed."

# ===================================================================================
# STEP 0: Manual Prerequisite Reminder
# ===================================================================================
echo "-----------------------------------------------------------------------------------"
echo "STEP 0: (Manual Prerequisite) Ensure any conflicting old (e.g., Windows-based) "
echo "        Function App and App Service Plan are deleted before running this for the first time."
echo "        Example commands (run MANUALLY if needed, replace 'myOldWindowsPlanName'):"
echo "          az functionapp delete --name \"$FUNCTION_APP_NAME\" --resource-group \"$RESOURCE_GROUP\""
echo "          az appservice plan delete --name \"myOldWindowsPlanName\" --resource-group \"$RESOURCE_GROUP\" --yes"
echo "-----------------------------------------------------------------------------------"
# echo "Pausing for 10 seconds to allow manual review/cancellation..."
# sleep 10


# ===================================================================================
# STEP 1: Deploy/Update Bicep Infrastructure
# ===================================================================================
echo "STEP 1: Deploying/Updating Bicep infrastructure..."

# Define names for App Service Plan and App Insights to be used in Bicep
# These can be static or derived. Ensure they match Bicep parameter expectations.
# If your Bicep expects these as parameters, define them here or ensure they are in .env
BICEP_APP_SERVICE_PLAN_NAME="myAppServicePlanB1Linux-${FUNCTION_APP_NAME}" # Example: Make it unique
BICEP_APP_INSIGHTS_NAME="appinsights-${FUNCTION_APP_NAME}"     # Example: Make it unique

# Define Docker image details (can also be read from .env if preferred)
BICEP_DOCKER_IMAGE_BASE_NAME="extract-function"
BICEP_DOCKER_IMAGE_TAG="v1"

az deployment group create \
  --name "bicep-deploy-$(date +%s)-${FUNCTION_APP_NAME}" \
  --resource-group "$RESOURCE_GROUP" \
  --template-file ./infrastructure-as-code/main.bicep \
  --parameters \
    location="$LOCATION" \
    functionAppName="$FUNCTION_APP_NAME" \
    appServicePlanName="$BICEP_APP_SERVICE_PLAN_NAME" \
    appInsightsInstrumentationKey="$APPINSIGHTS_INSTRUMENTATIONKEY" \
    acrName="$ACR_NAME" \
    acrUsername="$DOCKER_REGISTRY_SERVER_USERNAME" \
    acrPassword="$DOCKER_REGISTRY_SERVER_PASSWORD" \
    dockerImageBaseName="$BICEP_DOCKER_IMAGE_BASE_NAME" \
    dockerImageTag="$BICEP_DOCKER_IMAGE_TAG" \
    storageConnectionString="$STORAGE_CONNECTION_STRING" \
    datasetsContainerName="$DATASETS_CONTAINER_NAME" \
    rawDataContainerName="$RAW_DATA_CONTAINER_NAME" \
    transformQueueName="$TRANSFORM_QUEUE_NAME" \
    functionsWorkerRuntime="$FUNCTIONS_WORKER_RUNTIME" \
    websitesEnableAppServiceStorage="$WEBSITES_ENABLE_APP_SERVICE_STORAGE" \
  --debug # Keep --debug for troubleshooting Bicep deployment issues

echo "Bicep deployment finished."
echo "-----------------------------------------------------------------------------------"


# ===================================================================================
# STEP 2: Docker Image Build and Push
# ===================================================================================
echo "STEP 2: Logging into Azure ACR..."
az acr login --name "$ACR_NAME"

echo "STEP 3: Getting ACR login server (raw name)..."
ACR_LOGIN_SERVER_RAW=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)

# Construct the full image name, ensuring it matches what Bicep expects
IMAGE_NAME_TO_BUILD_AND_PUSH="${ACR_LOGIN_SERVER_RAW}/${BICEP_DOCKER_IMAGE_BASE_NAME}:${BICEP_DOCKER_IMAGE_TAG}"

echo "STEP 4: Building Docker image: $IMAGE_NAME_TO_BUILD_AND_PUSH ..."
# Ensure your Dockerfile is in the './extract_function/' directory relative to this script
docker build -t "$IMAGE_NAME_TO_BUILD_AND_PUSH" ./extract_function/

echo "STEP 5: Pushing Docker image to ACR: $IMAGE_NAME_TO_BUILD_AND_PUSH ..."
docker push "$IMAGE_NAME_TO_BUILD_AND_PUSH"

echo "Docker image build and push complete."
echo "-----------------------------------------------------------------------------------"


# ===================================================================================
# STEP 6: Check/Create Storage Account Resources (Containers and Queue)
# ===================================================================================
echo "STEP 6: Checking and creating Storage Account resources (if needed)..."

echo "Checking if '$RAW_DATA_CONTAINER_NAME' container exists in storage account '$STORAGE_ACCOUNT_NAME'..."
if ! az storage container show --name "$RAW_DATA_CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --connection-string "$STORAGE_CONNECTION_STRING" &>/dev/null; then
  echo "Creating '$RAW_DATA_CONTAINER_NAME' container..."
  az storage container create \
    --name "$RAW_DATA_CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --connection-string "$STORAGE_CONNECTION_STRING"
else
  echo "'$RAW_DATA_CONTAINER_NAME' container already exists."
fi

echo "Checking if '$DATASETS_CONTAINER_NAME' container exists in storage account '$STORAGE_ACCOUNT_NAME'..."
if ! az storage container show --name "$DATASETS_CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --connection-string "$STORAGE_CONNECTION_STRING" &>/dev/null; then
  echo "Creating '$DATASETS_CONTAINER_NAME' container..."
  az storage container create \
    --name "$DATASETS_CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --connection-string "$STORAGE_CONNECTION_STRING"
else
  echo "'$DATASETS_CONTAINER_NAME' container already exists."
fi

echo "Checking if '$TRANSFORM_QUEUE_NAME' queue exists in storage account '$STORAGE_ACCOUNT_NAME'..."
if ! az storage queue show --name "$TRANSFORM_QUEUE_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --connection-string "$STORAGE_CONNECTION_STRING" &>/dev/null; then
  echo "Creating '$TRANSFORM_QUEUE_NAME' queue..."
  az storage queue create \
    --name "$TRANSFORM_QUEUE_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --connection-string "$STORAGE_CONNECTION_STRING"
else
  echo "'$TRANSFORM_QUEUE_NAME' queue already exists."
fi
echo "Storage Account resource check/creation complete."
echo "-----------------------------------------------------------------------------------"


# ===================================================================================
# Final Message
# ===================================================================================
echo "✅ Deployment script finished successfully!"
echo "   - Bicep infrastructure deployed/updated."
echo "   - Docker image '$IMAGE_NAME_TO_BUILD_AND_PUSH' pushed to ACR."
echo "   - Storage resources checked/created."
echo ""
echo "Function App URL: https://${FUNCTION_APP_NAME}.azurewebsites.net"
echo "It might take a few minutes for the Function App to pull the latest image and start."
echo "You can monitor the logs in the Azure Portal (Function App -> Log stream or Container settings)."
echo "If the app doesn't start, check the 'Container settings' in Azure portal for any pull errors."
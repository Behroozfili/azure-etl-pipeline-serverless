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
# Sanity check for required environment variables
# ===================================================================================
echo "Performing sanity check for required environment variables..."
required_vars=(
  "LOCATION"
  "RESOURCE_GROUP"
  "STORAGE_ACCOUNT_NAME"
  "FUNCTION_APP_NAME"                 # نام فانکشن اپ Extract شما از .env
  "APPINSIGHTS_INSTRUMENTATIONKEY"
  "ACR_NAME"
  "DOCKER_REGISTRY_SERVER_USERNAME"
  "DOCKER_REGISTRY_SERVER_PASSWORD"
  "STORAGE_CONNECTION_STRING"
  "DATASETS_CONTAINER_NAME"
  "RAW_DATA_CONTAINER_NAME"
  "TRANSFORM_QUEUE_NAME"              # main.bicep هنوز این پارامتر را انتظار دارد
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
echo "STEP 0: (Manual Prerequisite) Ensure any conflicting old resources are deleted."
echo "        Example commands (run MANUALLY if needed, replace with actual old names):"
echo "          az functionapp delete --name \"myOldFunctionAppName\" --resource-group \"$RESOURCE_GROUP\""
echo "          az appservice plan delete --name \"myOldAppServicePlanName\" --resource-group \"$RESOURCE_GROUP\" --yes"
echo "-----------------------------------------------------------------------------------"
# echo "Pausing for 10 seconds to allow manual review/cancellation..."
# sleep 10


# ===================================================================================
# STEP 1: Deploy/Update Bicep Infrastructure (Focusing on Extract Function)
# ===================================================================================
echo "STEP 1: Deploying/Updating Bicep infrastructure (Focusing on Extract Function)..."

# Define a name for the App Service Plan.
# می‌توانید از نام فانکشن اپ اصلی برای ایجاد یک نام منحصر به فرد استفاده کنید یا یک نام ثابت انتخاب کنید.
BICEP_APP_SERVICE_PLAN_NAME="asp-${FUNCTION_APP_NAME}" # مثال

# Define Docker image details for Extract Function (مطابق با مقادیر قبلی شما)
BICEP_EXTRACT_DOCKER_IMAGE_BASE_NAME="extract-function"
BICEP_EXTRACT_DOCKER_IMAGE_TAG="v1"

# مقادیر ساختگی برای پارامترهای Transform Function که main.bicep انتظار دارد
# از آنجایی که ماژول transform کامنت شده است، این مقادیر منجر به ایجاد منابع transform نمی‌شوند.
PLACEHOLDER_TRANSFORM_FUNCTION_APP_NAME="placeholder-transform-fn"
PLACEHOLDER_TRANSFORM_DOCKER_IMAGE_BASE_NAME="placeholder-transform-img"
PLACEHOLDER_TRANSFORM_DOCKER_IMAGE_TAG="placeholder-v0"

az deployment group create \
  --name "bicep-deploy-$(date +%s)-${FUNCTION_APP_NAME}" \
  --resource-group "$RESOURCE_GROUP" \
  --template-file ./infrastructure-as-code/main.bicep \
  --parameters \
    location="$LOCATION" \
    appServicePlanName="$BICEP_APP_SERVICE_PLAN_NAME" \
    acrName="$ACR_NAME" \
    acrUsername="$DOCKER_REGISTRY_SERVER_USERNAME" \
    acrPassword="$DOCKER_REGISTRY_SERVER_PASSWORD" \
    appInsightsInstrumentationKey="$APPINSIGHTS_INSTRUMENTATIONKEY" \
    storageConnectionString="$STORAGE_CONNECTION_STRING" \
    functionsWorkerRuntime="$FUNCTIONS_WORKER_RUNTIME" \
    websitesEnableAppServiceStorage="$WEBSITES_ENABLE_APP_SERVICE_STORAGE" \
    extractFunctionAppName="$FUNCTION_APP_NAME" \
    extractDockerImageBaseName="$BICEP_EXTRACT_DOCKER_IMAGE_BASE_NAME" \
    extractDockerImageTag="$BICEP_EXTRACT_DOCKER_IMAGE_TAG" \
    datasetsContainerName="$DATASETS_CONTAINER_NAME" \
    rawDataContainerName="$RAW_DATA_CONTAINER_NAME" \
    transformFunctionAppName="$PLACEHOLDER_TRANSFORM_FUNCTION_APP_NAME" \
    transformDockerImageBaseName="$PLACEHOLDER_TRANSFORM_DOCKER_IMAGE_BASE_NAME" \
    transformDockerImageTag="$PLACEHOLDER_TRANSFORM_DOCKER_IMAGE_TAG" \
    transformQueueName="$TRANSFORM_QUEUE_NAME" \
  --debug # Keep --debug for troubleshooting Bicep deployment issues

echo "Bicep deployment finished."
echo "-----------------------------------------------------------------------------------"


# ===================================================================================
# STEP 2: Docker Image Build and Push (for Extract Function)
# ===================================================================================
echo "STEP 2: Logging into Azure ACR..."
az acr login --name "$ACR_NAME"

echo "STEP 3: Getting ACR login server (raw name)..."
ACR_LOGIN_SERVER_RAW=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)

# Construct the full image name for EXTRACT function
EXTRACT_IMAGE_NAME_TO_BUILD_AND_PUSH="${ACR_LOGIN_SERVER_RAW}/${BICEP_EXTRACT_DOCKER_IMAGE_BASE_NAME}:${BICEP_EXTRACT_DOCKER_IMAGE_TAG}"

echo "STEP 4: Building Docker image for Extract Function: $EXTRACT_IMAGE_NAME_TO_BUILD_AND_PUSH ..."
# Ensure your Dockerfile is in the './extract_function/' directory relative to this script
docker build -t "$EXTRACT_IMAGE_NAME_TO_BUILD_AND_PUSH" ./extract_function/

echo "STEP 5: Pushing Docker image for Extract Function to ACR: $EXTRACT_IMAGE_NAME_TO_BUILD_AND_PUSH ..."
docker push "$EXTRACT_IMAGE_NAME_TO_BUILD_AND_PUSH"

echo "Extract Docker image build and push complete."
echo "-----------------------------------------------------------------------------------"


# ===================================================================================
# STEP 6: Check/Create Storage Account Resources (Containers and Queue)
# ===================================================================================
# این بخش بدون تغییر باقی می‌ماند، چون کانتینرها و صف برای فانکشن extract یا آینده لازم هستند.
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
echo "   - Bicep infrastructure deployed/updated (focused on Extract Function)."
echo "   - Docker image '$EXTRACT_IMAGE_NAME_TO_BUILD_AND_PUSH' pushed to ACR."
echo "   - Storage resources checked/created."
echo ""
echo "Extract Function App URL: https://${FUNCTION_APP_NAME}.azurewebsites.net" # FUNCTION_APP_NAME از .env خوانده می‌شود
echo ""
echo "It might take a few minutes for the Extract Function App to pull the latest image and start."
echo "You can monitor the logs in the Azure Portal (Function App -> Log stream or Container settings)."
echo "If the app doesn't start, check the 'Container settings' in Azure portal for any pull errors."
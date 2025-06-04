#!/bin/bash

set -e

# Configuration - ویرایش کن طبق نیاز
RESOURCE_GROUP="etlResourceGroup"
LOCATION="eastus"
ACR_NAME="behetlregistry"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
DOCKER_IMAGE_NAME="extract-function"
DOCKER_IMAGE_TAG="v1"
FUNCTION_APP_NAME="behExtractFunc20240521"
BICEP_FILE="./infrastructure-as-code/main.bicep"
PARAMS_FILE="./infrastructure-as-code/parameters.json"

# Check dependencies
command -v az >/dev/null 2>&1 || { echo >&2 "az CLI is required but it's not installed. Aborting."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo >&2 "docker is required but it's not installed. Aborting."; exit 1; }

# Azure Login
echo "🔐 Logging into Azure..."
if ! az account show > /dev/null 2>&1; then
    az login
fi

# Check or create resource group
echo "🗂 Checking if resource group '$RESOURCE_GROUP' exists..."
if ! az group show --name $RESOURCE_GROUP > /dev/null 2>&1; then
    echo "Resource group not found. Creating..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
else
    echo "Resource group exists."
fi

# Docker build & push
echo "🐳 Building Docker image..."
docker build -t $ACR_LOGIN_SERVER/$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG ./extract_function


echo "🔐 Logging into Azure Container Registry..."
az acr login --name $ACR_NAME

echo "📤 Pushing Docker image to ACR..."
docker push $ACR_LOGIN_SERVER/$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG

# Get ACR password securely
echo "🔑 Retrieving ACR password..."
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

# Bicep deployment
echo "🚀 Deploying Bicep template..."
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file $BICEP_FILE \
  --parameters @$PARAMS_FILE \
  --parameters acrPassword=$ACR_PASSWORD

echo "✅ Extract deployment completed successfully!"

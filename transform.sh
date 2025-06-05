#!/bin/bash
set -e

# Build and push the Docker image for the Transform function.

# --- Configuration ---
ACR_NAME="${ACR_NAME:-behetlregistry}"
IMAGE_BASE_NAME="${TRANSFORM_IMAGE_BASE_NAME:-transform-function}"
IMAGE_TAG="${TRANSFORM_IMAGE_TAG:-v1}"
TRANSFORM_FUNCTION_CODE_DIR="transform_function"
DOCKERFILE_PATH="${TRANSFORM_FUNCTION_CODE_DIR}/Dockerfile"
# ----------------------

error_exit() {
    echo "ERROR: $1" >&2
    exit 1
}

# Check project root structure
if [ ! -d "$TRANSFORM_FUNCTION_CODE_DIR" ] || [ ! -f "$DOCKERFILE_PATH" ]; then
    error_exit "Missing function directory or Dockerfile. Run this script from the project root."
fi

ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
FULL_IMAGE_NAME="${ACR_LOGIN_SERVER}/${IMAGE_BASE_NAME}:${IMAGE_TAG}"
BUILD_CONTEXT="."

echo "--- Building & Pushing Transform Function Image ---"
echo "ACR Login Server: ${ACR_LOGIN_SERVER}"
echo "Image Name:       ${FULL_IMAGE_NAME}"
echo "Dockerfile Path:  ${DOCKERFILE_PATH}"
echo "Build Context:    ${BUILD_CONTEXT}"
echo "----------------------------------------------------"

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
  error_exit "Docker is not running."
fi

# Login to Azure Container Registry
echo "Logging in to ACR: ${ACR_NAME}..."
if az acr login --name "${ACR_NAME}"; then
    echo "Login successful."
else
    error_exit "ACR login failed. Make sure you're logged in to Azure CLI."
fi

# Build Docker image
echo "Building image..."
if docker build -t "${FULL_IMAGE_NAME}" -f "${DOCKERFILE_PATH}" "${BUILD_CONTEXT}"; then
    echo "Build completed."
else
    error_exit "Docker build failed."
fi

# Push Docker image
echo "Pushing image to ACR..."
if docker push "${FULL_IMAGE_NAME}"; then
    echo "Push successful."
else
    error_exit "Docker push failed."
fi

echo "----------------------------------------------------"
echo "Image build and push complete: ${FULL_IMAGE_NAME}"
echo "----------------------------------------------------"

exit 0

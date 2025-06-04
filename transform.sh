#!/bin/bash

# transform.sh
# اسکریپتی برای ساخت و پوش کردن ایمیج Docker فانکشن Transform.
# این اسکریپت باید از ریشه پروژه اجرا شود.

# --- پیکربندی ---
# این مقادیر را می‌توانید مستقیماً اینجا ویرایش کنید، یا به عنوان متغیر محیطی پاس دهید،
# یا به عنوان آرگومان به اسکریپت بدهید (پیاده‌سازی نشده در این نسخه ساده).

# نام Azure Container Registry شما
ACR_NAME="${ACR_NAME:-behetlregistry}" # <<< مقدار شما اینجا تنظیم شده است

# نام پایه ایمیج برای فانکشن Transform (مطابق با پارامتر Bicep: transformDockerImageBaseName)
IMAGE_BASE_NAME="${TRANSFORM_IMAGE_BASE_NAME:-transform-function}" # مقدار پیش‌فرض از Bicep شما

# تگ ایمیج (مطابق با پارامتر Bicep: transformDockerImageTag)
IMAGE_TAG="${TRANSFORM_IMAGE_TAG:-v1}" # مقدار پیش‌فرض از Bicep شما

# مسیر نسبی به پوشه کد فانکشن Transform از ریشه پروژه
TRANSFORM_FUNCTION_CODE_DIR="transform_function"

# مسیر نسبی به Dockerfile فانکشن Transform از ریشه پروژه
DOCKERFILE_PATH="${TRANSFORM_FUNCTION_CODE_DIR}/Dockerfile"

# --- پایان پیکربندی ---


# تابع برای نمایش پیام خطا و خروج
error_exit() {
    echo "ERROR: $1" >&2
    exit 1
}

# بررسی اینکه آیا در ریشه پروژه هستیم (با بررسی وجود پوشه transform function)
if [ ! -d "$TRANSFORM_FUNCTION_CODE_DIR" ] || [ ! -f "$DOCKERFILE_PATH" ]; then
    error_exit "This script must be run from the project root directory, and the transform function directory ('${TRANSFORM_FUNCTION_CODE_DIR}') and its Dockerfile ('${DOCKERFILE_PATH}') must exist."
fi

# دیگر نیازی به بررسی مقدار پیش‌فرض ACR_NAME نیست چون مستقیماً تنظیم شده
# if [ "$ACR_NAME" == "your_acr_name" ]; then ...

# متغیرهای مشتق شده
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
FULL_IMAGE_NAME="${ACR_LOGIN_SERVER}/${IMAGE_BASE_NAME}:${IMAGE_TAG}"
BUILD_CONTEXT="." # Build context ریشه پروژه است

echo "--- Transform Function Docker Build & Push ---"
echo "ACR Login Server: ${ACR_LOGIN_SERVER}"
echo "Full Image Name:  ${FULL_IMAGE_NAME}"
echo "Dockerfile Path:  ${DOCKERFILE_PATH}"
echo "Build Context:    ${BUILD_CONTEXT}"
echo "---------------------------------------------"

# 0. بررسی اینکه Docker در حال اجراست
if ! docker info > /dev/null 2>&1; then
  error_exit "Docker daemon is not running. Please start Docker."
fi

# 1. لاگین به Azure Container Registry
# این بخش فرض می‌کند که شما قبلاً `az login` کرده‌اید.
echo "Attempting to login to ACR: ${ACR_NAME}..."
if az acr login --name "${ACR_NAME}"; then
    echo "Successfully logged in to ACR: ${ACR_NAME}."
else
    error_exit "Failed to login to ACR: ${ACR_NAME}. Please ensure you are logged into Azure CLI and have permissions."
fi

# 2. ساخت ایمیج Docker
# از ریشه پروژه (BUILD_CONTEXT) با استفاده از Dockerfile مشخص شده.
echo "Building Docker image: ${FULL_IMAGE_NAME}..."
if docker build -t "${FULL_IMAGE_NAME}" -f "${DOCKERFILE_PATH}" "${BUILD_CONTEXT}"; then
    echo "Docker image built successfully: ${FULL_IMAGE_NAME}"
else
    error_exit "Docker build failed."
fi

# 3. پوش کردن ایمیج Docker به ACR
echo "Pushing Docker image to ${ACR_LOGIN_SERVER}..."
if docker push "${FULL_IMAGE_NAME}"; then
    echo "Docker image pushed successfully: ${FULL_IMAGE_NAME}"
else
    error_exit "Docker push failed."
fi

echo "---------------------------------------------"
echo "Transform function Docker image build and push complete!"
echo "Image: ${FULL_IMAGE_NAME}"
echo "---------------------------------------------"

exit 0
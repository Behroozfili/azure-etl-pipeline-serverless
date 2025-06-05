#!/bin/bash
set -e

# Load environment variables from .env if available
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE"
    export $(grep -v '^#' $ENV_FILE | grep -v '^$' | xargs)
else
    echo "Warning: $ENV_FILE not found. Using existing environment variables."
fi

# Variables with defaults, can be overridden by environment or .env
LOAD_FUNCTION_DIR="load_function"
DOCKERFILE_PATH="${LOAD_FUNCTION_DIR}/Dockerfile"

IMAGE_NAME="${IMAGE_NAME:-myproject/load-function}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_NAME="${CONTAINER_NAME:-load-function-container}"
HOST_PORT="${HOST_PORT:-7072}"

LOAD_QUEUE_NAME="${LOAD_QUEUE_NAME:-load-input-queue}"
DATASETS_CONTAINER_NAME="${DATASETS_CONTAINER_NAME:-datasets}"
FINAL_OUTPUT_CONTAINER_NAME="${FINAL_OUTPUT_CONTAINER_NAME:-finaloutput}"

# Check mandatory secret variable
if [ -z "${AZURE_STORAGE_CONNECTION_STRING}" ]; then
    echo "Error: AZURE_STORAGE_CONNECTION_STRING is not set."
    echo "Set it in $ENV_FILE or export it in your environment."
    exit 1
fi

# Build Docker image
build_image() {
    echo "Building Docker image ${IMAGE_NAME}:${IMAGE_TAG}..."
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f "${DOCKERFILE_PATH}" .
    echo "Docker image built."
}

# Stop and remove existing container if running
stop_existing_container() {
    if [ "$(docker ps -q -f name=${CONTAINER_NAME})" ]; then
        echo "Stopping existing container ${CONTAINER_NAME}..."
        docker stop "${CONTAINER_NAME}"
    fi
    if [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
        echo "Removing existing container ${CONTAINER_NAME}..."
        docker rm "${CONTAINER_NAME}"
    fi
}

# Run the Docker container with environment variables and port mapping
run_container() {
    echo "Starting container ${CONTAINER_NAME} from image ${IMAGE_NAME}:${IMAGE_TAG}..."
    echo "Load function available at http://localhost:${HOST_PORT}"
    docker run -d --rm \
        -p "${HOST_PORT}:80" \
        -e "AzureWebJobsStorage=${AZURE_STORAGE_CONNECTION_STRING}" \
        -e "LOAD_QUEUE_NAME=${LOAD_QUEUE_NAME}" \
        -e "DATASETS_CONTAINER_NAME=${DATASETS_CONTAINER_NAME}" \
        -e "FINAL_OUTPUT_CONTAINER_NAME=${FINAL_OUTPUT_CONTAINER_NAME}" \
        -e "FUNCTIONS_WORKER_RUNTIME=python" \
        -e "AzureFunctionsJobHost__Logging__Console__IsEnabled=true" \
        --name "${CONTAINER_NAME}" \
        "${IMAGE_NAME}:${IMAGE_TAG}"
    echo "Container started. Use 'docker logs -f ${CONTAINER_NAME}' to view logs."
}

# Send test message to Azure Storage Queue
send_test_message_to_queue() {
    local blob_name="$1"
    if [ -z "$blob_name" ]; then
        echo "No blob name provided."
        return 1
    fi
    echo "Sending test message '${blob_name}' to queue ${LOAD_QUEUE_NAME}..."
    az storage message put \
        --queue-name "${LOAD_QUEUE_NAME}" \
        --content "${blob_name}" \
        --connection-string "${AZURE_STORAGE_CONNECTION_STRING}"
    if [ $? -eq 0 ]; then
        echo "Message sent successfully."
    else
        echo "Failed to send message. Check connection string and Azure CLI."
    fi
}

# Main control flow
case "$1" in
    build)
        build_image
        ;;
    run)
        stop_existing_container
        run_container
        ;;
    send_message)
        if [ -z "$2" ]; then
            echo "Usage: $0 send_message <blob_name>"
            exit 1
        fi
        send_test_message_to_queue "$2"
        ;;
    full_test)
        build_image
        stop_existing_container
        run_container
        sleep 10
        send_test_message_to_queue "${2:-sample-test-blob-for-load.txt}"
        ;;
    *)
        build_image
        stop_existing_container
        run_container
        echo "---"
        echo "To send a test message:"
        echo "$0 send_message your-blob-name.txt"
        ;;
esac

echo "Done."

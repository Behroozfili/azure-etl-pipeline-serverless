import logging
import azure.functions as func
import os
from azure.storage.blob import BlobServiceClient

STORAGE_CONNECTION_STRING_ENV_VAR = "AzureWebJobsStorage"
DATASETS_CONTAINER_NAME_ENV_VAR = "DATASETS_CONTAINER_NAME"
FINAL_OUTPUT_CONTAINER_NAME_ENV_VAR = "FINAL_OUTPUT_CONTAINER_NAME"

def main(msg: func.QueueMessage) -> None:
    logging.info(f"Python Queue trigger function processed a message for Load Function: {msg.get_body().decode('utf-8')}")

    blob_name_to_load = "UNKNOWN_BLOB"
    try:
        blob_name_to_load = msg.get_body().decode('utf-8')
        if not blob_name_to_load:
            logging.error("Queue message body is empty. Cannot determine blob to load.")
            return

        logging.info(f"Load function triggered for blob: {blob_name_to_load}")

        storage_connection_string = os.environ.get(STORAGE_CONNECTION_STRING_ENV_VAR)
        source_container_name = os.environ.get(DATASETS_CONTAINER_NAME_ENV_VAR)
        destination_container_name = os.environ.get(FINAL_OUTPUT_CONTAINER_NAME_ENV_VAR)

        if not all([storage_connection_string, source_container_name, destination_container_name]):
            logging.error("One or more environment variables for storage are missing. Check App Settings (DATASETS_CONTAINER_NAME, FINAL_OUTPUT_CONTAINER_NAME).")
            return

        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)

        source_blob_client = blob_service_client.get_blob_client(
            container=source_container_name,
            blob=blob_name_to_load
        )

        destination_blob_client = blob_service_client.get_blob_client(
            container=destination_container_name,
            blob=blob_name_to_load
        )

        if not source_blob_client.exists():
            logging.error(f"Source blob '{blob_name_to_load}' not found in container '{source_container_name}'.")
            return

        logging.info(f"Starting copy of blob '{blob_name_to_load}' from '{source_container_name}' to '{destination_container_name}'.")

        source_blob_data = source_blob_client.download_blob().readall()
        destination_blob_client.upload_blob(source_blob_data, overwrite=True)

        logging.info(f"Successfully loaded/copied blob '{blob_name_to_load}' to container '{destination_container_name}'.")

    except UnicodeDecodeError:
        logging.error("Could not decode queue message body as UTF-8.")
    except Exception as e:
        logging.error(f"Error processing blob '{blob_name_to_load}' in Load function: {str(e)}")
        raise

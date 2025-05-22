import logging
import azure.functions as func
import os

INPUT_CONTAINER_NAME = os.environ.get("DATASETS_CONTAINER_NAME", "datasets")
OUTPUT_CONTAINER_NAME = os.environ.get("RAW_DATA_CONTAINER_NAME", "raw-data")
OUTPUT_QUEUE_NAME = os.environ.get("TRANSFORM_QUEUE_NAME", "transform-queue")

def main(inputBlob: func.InputStream, outputBlob: func.Out[bytes], outputQueueItem: func.Out[str]):
    logging.info(f"Python Blob trigger function processed blob \n"
                 f"Name: {inputBlob.name}\n"
                 f"Blob Size: {inputBlob.length} bytes")

    try:
        blob_content = inputBlob.read()
        outputBlob.set(blob_content)
        logging.info(f"Successfully copied blob '{inputBlob.name}' to container '{OUTPUT_CONTAINER_NAME}'.")

        file_name_only = inputBlob.name.split('/')[-1]
        message_for_queue = f"{OUTPUT_CONTAINER_NAME}/{file_name_only}"
        outputQueueItem.set(message_for_queue)
        logging.info(f"Sent message to queue '{OUTPUT_QUEUE_NAME}': {message_for_queue}")

    except Exception as e:
        logging.error(f"Error processing blob {inputBlob.name}: {str(e)}")
        raise

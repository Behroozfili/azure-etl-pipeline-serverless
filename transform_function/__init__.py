import logging
import azure.functions as func
import os
import sys

# Add project root to sys.path for importing databricks module
current_function_dir = os.path.dirname(__file__)
project_root_dir = os.path.abspath(os.path.join(current_function_dir, '..', '..'))
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

try:
    from databricks.notebooks.data_transformation_notebook import perform_basic_data_transformation
    DATABRICKS_MODULE_LOADED = True
    logging.info("Successfully imported 'perform_basic_data_transformation' from databricks module.")
except ImportError as e:
    logging.error(f"Failed to import 'perform_basic_data_transformation': {e}")
    logging.error(f"Current sys.path: {sys.path}")
    logging.error(f"Project root considered: {project_root_dir}")
    DATABRICKS_MODULE_LOADED = False

    # Fallback function if databricks module fails to load
    def perform_basic_data_transformation(raw_data_str: str, blob_name: str) -> str:
        logging.warning(f"[Fallback] Databricks module not loaded for blob: {blob_name}. Spark ETL cannot run.")
        return f"ERROR: Databricks module for Spark ETL could not be loaded. Blob: {blob_name}"

# Environment variable names
STORAGE_ACCOUNT_NAME_ENV_VAR = "STORAGE_ACCOUNT_NAME"
RAW_DATA_CONTAINER_NAME_ENV_VAR = "RAW_DATA_CONTAINER_NAME"
DATASETS_CONTAINER_NAME_ENV_VAR = "DATASETS_CONTAINER_NAME"
AZURE_STORAGE_ACCOUNT_KEY_ENV_VAR = "AZURE_STORAGE_ACCOUNT_KEY"

def main(msg: func.QueueMessage, loadQueueOutput: func.Out[str]) -> None:
    logging.info('Python Queue trigger function processed a Transform Function request.')

    if not DATABRICKS_MODULE_LOADED:
        logging.error("Databricks module (Spark ETL) is not loaded. Cannot proceed.")
        loadQueueOutput.set("ERROR: Spark ETL module failed to load.")
        return

    blob_name_from_queue = "UNKNOWN_BLOB_TRIGGER"
    try:
        blob_name_from_queue = msg.get_body().decode('utf-8')
        logging.info(f"Received message to trigger Spark ETL, signal from: {blob_name_from_queue}")

        if not blob_name_from_queue:
            logging.error("Queue message body is empty or invalid trigger.")
            return

        # Read required environment variables
        storage_account_name = os.environ.get(STORAGE_ACCOUNT_NAME_ENV_VAR)
        raw_data_container = os.environ.get(RAW_DATA_CONTAINER_NAME_ENV_VAR)
        datasets_container = os.environ.get(DATASETS_CONTAINER_NAME_ENV_VAR)
        storage_account_key = os.environ.get(AZURE_STORAGE_ACCOUNT_KEY_ENV_VAR)

        if not all([storage_account_name, raw_data_container, datasets_container, storage_account_key]):
            missing_vars = [var for var, val in {
                STORAGE_ACCOUNT_NAME_ENV_VAR: storage_account_name,
                RAW_DATA_CONTAINER_NAME_ENV_VAR: raw_data_container,
                DATASETS_CONTAINER_NAME_ENV_VAR: datasets_container,
                AZURE_STORAGE_ACCOUNT_KEY_ENV_VAR: storage_account_key
            }.items() if not val]
            error_msg = f"Missing critical environment variables for Spark ETL: {', '.join(missing_vars)}. Ensure they are set in Function App configuration."
            logging.error(error_msg)
            loadQueueOutput.set(f"ERROR: Configuration incomplete. {error_msg}")
            return

        logging.info(f"Invoking Spark ETL process for trigger: {blob_name_from_queue}")
        etl_output_message = perform_basic_data_transformation("", blob_name_from_queue)

        if not etl_output_message or "ERROR" in etl_output_message.upper():
            logging.error(f"Spark ETL process reported an error or empty result: {etl_output_message}")
            loadQueueOutput.set(etl_output_message if etl_output_message else "ERROR: Spark ETL returned empty message.")
            return

        loadQueueOutput.set(etl_output_message)
        logging.info(f"Successfully triggered Spark ETL. Output/status sent to Load queue: {etl_output_message}")

    except UnicodeDecodeError:
        logging.error(f"Could not decode queue message body as UTF-8: {msg.get_body()}")
    except ValueError as ve:
        logging.error(f"ValueError during Spark ETL orchestration for '{blob_name_from_queue}': {ve}")
        loadQueueOutput.set(f"ERROR: Configuration or runtime error in Spark ETL. Details: {str(ve)}")
    except Exception as e:
        logging.error(f"Unhandled error in Transform function for trigger '{blob_name_from_queue}': {e}", exc_info=True)
        loadQueueOutput.set(f"ERROR: Unhandled exception in Transform function. Details: {str(e)}")

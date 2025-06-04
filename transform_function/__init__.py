# 09.transform_function/__init__.py
import logging
import azure.functions as func
import os
import sys

# --- مسیردهی برای وارد کردن ماژول از پوشه databricks ---
# این بخش کلیدی است تا فانکشن بتواند ماژول databricks را پیدا کند.
# __file__ به این فایل (__init__.py) در 09.transform_function اشاره دارد.
# ما نیاز داریم به ریشه پروژه (یک سطح بالاتر از 09.transform_function) برویم
# تا بتوانیم 12.databricks را به عنوان یک پکیج ببینیم.
# این مسیر باید در Dockerfile هم به درستی تنظیم شود (با کپی کردن کل پروژه یا بخش‌های لازم).

# مسیر به پوشه فانکشن فعلی (09.transform_function)
current_function_dir = os.path.dirname(__file__)
# مسیر به ریشه پروژه (مثلاً پوشه‌ای که 06.infrastructure-as-code، 07.shared و ... در آن هستند)
project_root_dir = os.path.abspath(os.path.join(current_function_dir, '..'))

# اضافه کردن ریشه پروژه به sys.path اگر قبلاً وجود ندارد
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)
# -------------------------------------------------------------

# حالا سعی می‌کنیم تابع را از ماژول databricks وارد کنیم
try:
    # فرض می‌کنیم 12.databricks/notebooks/ یک مسیر قابل ایمپورت است
    # این نیاز به یک __init__.py خالی در 12.databricks/ و 12.databricks/notebooks/
    # ممکن است داشته باشد، یا اینکه ساختار پوشه Docker شما به گونه‌ای باشد که پایتون آن را پیدا کند.
    # ساده‌ترین راه این است که فرض کنیم PYTHONPATH در Dockerfile درست تنظیم شده.
    from databricks.notebooks.data_transformation_notebook import perform_basic_data_transformation
    DATABRICKS_MODULE_LOADED = True
except ImportError as e:
    logging.error(f"CRITICAL: Failed to import 'perform_basic_data_transformation' from databricks module: {e}")
    logging.error(f"Current sys.path: {sys.path}")
    logging.error(f"Project root considered: {project_root_dir}")
    DATABRICKS_MODULE_LOADED = False
    # به عنوان یک fallback بسیار ساده، اگر ایمپورت ناموفق بود:
    def perform_basic_data_transformation(raw_data_str: str, blob_name: str) -> str:
        logging.warning(f"[FallbackLogic] Databricks module not loaded. Using fallback for: {blob_name}")
        return f"FALLBACK_TRANSFORMED: {raw_data_str.strip().upper()}"

# --- متغیرهای محیطی برای ارتباط با Storage ---
STORAGE_CONNECTION_STRING_ENV_VAR = "AzureWebJobsStorage"
RAW_DATA_CONTAINER_NAME_ENV_VAR = "RAW_DATA_CONTAINER_NAME"
DATASETS_CONTAINER_NAME_ENV_VAR = "DATASETS_CONTAINER_NAME"
# ---------------------------------------------

def main(msg: func.QueueMessage) -> None:
    logging.info('Python Queue trigger function processed a queue item for Transform Function.')
    if not DATABRICKS_MODULE_LOADED:
        logging.warning("Databricks transformation module was not loaded. Using fallback logic.")

    blob_name_from_queue = "UNKNOWN_BLOB"

    try:
        blob_name_from_queue = msg.get_body().decode('utf-8')
        logging.info(f"Received message to transform blob: {blob_name_from_queue}")

        if not blob_name_from_queue:
            logging.error("Queue message body is empty or not a valid blob name.")
            return

        storage_connection_string = os.environ.get(STORAGE_CONNECTION_STRING_ENV_VAR)
        raw_data_container = os.environ.get(RAW_DATA_CONTAINER_NAME_ENV_VAR)
        datasets_container = os.environ.get(DATASETS_CONTAINER_NAME_ENV_VAR)

        if not all([storage_connection_string, raw_data_container, datasets_container]):
            logging.error(f"Missing one or more storage env vars. Ensure {RAW_DATA_CONTAINER_NAME_ENV_VAR}, {DATASETS_CONTAINER_NAME_ENV_VAR} are set in App Settings.")
            return

        from azure.storage.blob import BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        
        raw_blob_client = blob_service_client.get_blob_client(container=raw_data_container, blob=blob_name_from_queue)
        
        logging.info(f"Reading blob: '{blob_name_from_queue}' from container: '{raw_data_container}'")
        try:
            downloader = raw_blob_client.download_blob(encoding='UTF-8')
            input_blob_data_str = downloader.readall()
            logging.info(f"Read {len(input_blob_data_str)} chars from raw blob.")
        except Exception as e:
            logging.error(f"Failed to read blob '{blob_name_from_queue}'. Error: {str(e)}")
            raise

        # --- فراخوانی تابع تبدیل از ماژول "Databricks" ---
        transformed_data_str = perform_basic_data_transformation(input_blob_data_str, blob_name_from_queue)
        # -------------------------------------------------

        if not transformed_data_str:
            logging.warning(f"Transformation (from databricks module or fallback) resulted in empty data for {blob_name_from_queue}. Skipping write.")
            return

        transformed_data_bytes = transformed_data_str.encode('utf-8')

        transformed_blob_client = blob_service_client.get_blob_client(container=datasets_container, blob=blob_name_from_queue)
        logging.info(f"Writing transformed blob: '{blob_name_from_queue}' to container: '{datasets_container}'")
        transformed_blob_client.upload_blob(transformed_data_bytes, overwrite=True)
        logging.info(f"Successfully wrote {len(transformed_data_bytes)} bytes to transformed blob.")
        
        logging.info(f"Successfully transformed blob: {blob_name_from_queue}")

    except UnicodeDecodeError:
        logging.error("Could not decode queue message body as UTF-8.")
    except ValueError as ve:
        logging.error(f"ValueError for blob '{blob_name_from_queue}': {str(ve)}")
    except Exception as e:
        logging.error(f"General error for blob '{blob_name_from_queue}': {str(e)}")
        raise
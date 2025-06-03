# ./transform_function/__init__.py

import azure.functions as func # Main Azure Functions library
import os # For accessing environment variables
import logging # For logging messages
import json # For working with JSON data
from databricks_sdk import WorkspaceClient # Databricks SDK for interacting with Databricks API
from databricks_sdk.service.jobs import ( # Specific classes from Databricks SDK for job submission
    NotebookTask, # Defines a notebook task
    Task, # General task definition
    JobCluster, # Defines a new job cluster
    AutoScale # For defining autoscale properties for the cluster
)
from azure.storage.queue import QueueServiceClient # Azure Storage Queue SDK for sending messages

# --- Databricks Cluster Configuration - Read from environment variables ---
# These variables are set in the Function App's application settings (via Bicep)
DATABRICKS_NODE_TYPE_ID = os.environ.get("DATABRICKS_NODE_TYPE_ID", "Standard_F4s_v2") # Default if not set
DATABRICKS_SPARK_VERSION = os.environ.get("DATABRICKS_SPARK_VERSION", "13.3.x-scala2.12") # Default Spark version
DATABRICKS_MIN_WORKERS = int(os.environ.get("DATABRICKS_MIN_WORKERS", "0")) # Default min workers
DATABRICKS_MAX_WORKERS = int(os.environ.get("DATABRICKS_MAX_WORKERS", "0")) # Default max workers (0,0 for single node)
DATABRICKS_RUN_TIMEOUT_SECONDS = int(os.environ.get("DATABRICKS_RUN_TIMEOUT_SECONDS", 1800)) # Default 30 minutes

# --- Queue Information for Triggering the Load Function ---
LOAD_QUEUE_NAME = os.environ.get("LOAD_TRIGGER_QUEUE_NAME") # Name of the queue for the Load function
STORAGE_CONNECTION_STRING_FOR_QUEUES = os.environ.get("AzureWebJobsStorage") # Storage connection string for queues

def main(msg: func.QueueMessage) -> None:
    """
    Azure Function triggered by a queue message to orchestrate a Databricks notebook job
    for data transformation and then triggers the load function.
    """
    run_id = None # Initialize Databricks run_id for logging purposes
    try:
        message_body = msg.get_body().decode("utf-8") # Get the message content from the queue
        logging.info(f"Transform Function: Processing queue item: {message_body}")

        # The message_body can be a simple trigger string or a JSON object with more details.
        # For the Olist dataset, it might just be a notification that data is ready.
        # The notebook itself knows which files to process from the raw_data_container.
        input_trigger_file_context = message_body # Use the message as a contextual name for the run

        # --- Read Configuration from Environment Variables ---
        databricks_host = os.environ["DATABRICKS_HOST"]
        databricks_token = os.environ["DATABRICKS_TOKEN"]
        notebook_path = os.environ["DATABRICKS_NOTEBOOK_PATH"]
        raw_container = os.environ["RAW_DATA_CONTAINER_NAME"]
        processed_container = os.environ["PROCESSED_DATA_CONTAINER_NAME"]
        storage_account_name = os.environ["STORAGE_ACCOUNT_NAME"]

        # --- Prepare Parameters for the Databricks Notebook ---
        # The notebook will use these parameters to locate data and configure its run.
        notebook_params = {
            "input_file_name": input_trigger_file_context, # Contextual name, notebook might not use it directly for Olist
            "raw_data_container": raw_container,
            "processed_data_container": processed_container,
            "storage_account_name": storage_account_name
        }
        logging.info(f"Transform Function: Databricks notebook parameters: {json.dumps(notebook_params)}")

        # --- Initialize Databricks Workspace Client ---
        w = WorkspaceClient(host=databricks_host, token=databricks_token)

        # --- Define the New Job Cluster for Databricks ---
        # This cluster will be created on-demand for the job and terminated afterwards.
        new_cluster_definition = JobCluster(
            job_cluster_key='transform_etl_job_cluster', # An arbitrary key for this cluster definition within the job
            new_cluster={ # Specification for the new cluster
                "spark_version": DATABRICKS_SPARK_VERSION,
                "node_type_id": DATABRICKS_NODE_TYPE_ID,
                "enable_elastic_disk": True, # Recommended for better disk performance
            }
        )

        # Configure worker nodes (single node or autoscale)
        if DATABRICKS_MIN_WORKERS == 0 and DATABRICKS_MAX_WORKERS == 0:
            # Configure for a single-node cluster (driver only)
            new_cluster_definition.new_cluster['num_workers'] = 0
            new_cluster_definition.new_cluster['spark_conf'] = {"spark.databricks.cluster.profile": "singleNode"}
            logging.info("Transform Function: Configuring for a Single Node Databricks Cluster.")
        else:
            # Configure for a cluster with worker nodes (autoscaling)
            new_cluster_definition.new_cluster['autoscale'] = AutoScale(
                min_workers=DATABRICKS_MIN_WORKERS,
                max_workers=DATABRICKS_MAX_WORKERS
            )
            logging.info(f"Transform Function: Configuring Databricks cluster with autoscale: min_workers={DATABRICKS_MIN_WORKERS}, max_workers={DATABRICKS_MAX_WORKERS}")

        logging.info(f"Transform Function: Submitting notebook to Databricks with new cluster definition: {new_cluster_definition.as_dict()}")

        # --- Submit the Databricks Notebook Run ---
        # Create a somewhat unique run name for better tracking in Databricks UI
        safe_trigger_name_part = "".join(c if c.isalnum() or c in ['_','-'] else '_' for c in input_trigger_file_context)
        unique_run_name = f"olist_transform_run_{safe_trigger_name_part[:50]}" # Truncate to avoid overly long names

        run_submission = w.jobs.submit_run(
            run_name=unique_run_name,
            tasks=[ # Define the tasks for this run (in this case, a single notebook task)
                Task(
                    task_key='olist_notebook_task', # Arbitrary key for this task
                    job_cluster_key='transform_etl_job_cluster', # Links to the job cluster defined above
                    notebook_task=NotebookTask(
                        notebook_path=notebook_path,
                        base_parameters=notebook_params # Pass parameters to the notebook
                    )
                )
            ],
            job_clusters=[new_cluster_definition], # Provide the job cluster definition
            timeout_seconds=DATABRICKS_RUN_TIMEOUT_SECONDS # Set a timeout for the entire run
        )
        run_id = run_submission.run_id # Get the run_id from the submission response
        
        # Constructing a probable job_id for the URL. The actual job_id is part of the run_submission response if it's a one-time run of a pre-existing job.
        # For `submit_run` (which is like "Run Now" for a new job definition), `run_submission.job_id` might be None.
        # The URL structure is typically /#job/<job_id>/run/<run_id> or /#run/<run_id> for one-time runs.
        # Let's use a simpler URL for one-time runs if job_id is not present.
        run_url_job_id_part = f"job/{run_submission.job_id}/" if run_submission.job_id else ""
        run_url = f"{w.config.host}/#${run_url_job_id_part}run/{run_id}"
        logging.info(f"Transform Function: Databricks run submitted. Run ID: {run_id}, Run URL: {run_url}")


        # --- Wait for the Databricks Job to Complete ---
        # This will block the Azure Function until the Databricks job finishes or times out.
        logging.info(f"Transform Function: Waiting for Databricks run {run_id} to complete...")
        run_info = w.jobs.wait_get_run_job_terminated_or_skipped(run_id)
        life_cycle_state = run_info.state.life_cycle_state if run_info.state else "UNKNOWN_LIFECYCLE"
        result_state = run_info.state.result_state if run_info.state else "UNKNOWN_RESULT"

        logging.info(f"Transform Function: Databricks run {run_id} finished. LifeCycleState: {life_cycle_state}, ResultState: {result_state}")

        # --- Handle Databricks Job Outcome ---
        if result_state == "SUCCESS":
            logging.info(f"Transform Function: Databricks notebook run {run_id} completed successfully.")

            # If the Databricks job was successful, trigger the Load function by sending a message to its queue.
            if LOAD_QUEUE_NAME and STORAGE_CONNECTION_STRING_FOR_QUEUES:
                logging.info(f"Transform Function: Sending message to queue '{LOAD_QUEUE_NAME}' for Olist processed data.")
                queue_service_client = QueueServiceClient.from_connection_string(STORAGE_CONNECTION_STRING_FOR_QUEUES)
                queue_client = queue_service_client.get_queue_client(LOAD_QUEUE_NAME)
                
                # Message content for the Load function
                message_for_load_function = {
                    "dataset_name": "olist_ecommerce", # Identifier for the dataset
                    "processed_data_base_path": f"{processed_container}/olist_ecommerce_processed", # Base path of processed data
                    "status": "transformed_successfully",
                    "databricks_run_id": run_id
                }
                queue_client.send_message(json.dumps(message_for_load_function))
                logging.info(f"Transform Function: Message sent to '{LOAD_QUEUE_NAME}'.")
            else:
                logging.warning("Transform Function: LOAD_TRIGGER_QUEUE_NAME or AzureWebJobsStorage not configured. Cannot trigger next load step.")
        else:
            # If the Databricks job failed or was canceled
            error_message_detail = run_info.state.state_message if run_info.state and run_info.state.state_message else "Unknown error during Databricks run."
            error_message = f"Databricks notebook run {run_id} failed or was canceled. LifeCycleState: {life_cycle_state}, ResultState: {result_state}. Reason: {error_message_detail}"
            logging.error(f"Transform Function: {error_message}")
            raise Exception(error_message) # Raise an exception to mark the Azure Function execution as failed

    except Exception as e:
        # Catch any other exceptions during the Azure Function execution
        error_msg_final = f"Transform Function: Error during processing. Databricks Run ID (if available): {run_id}. Error: {str(e)}"
        logging.error(error_msg_final, exc_info=True) # Log the full exception info
        raise # Re-raise the exception to ensure Azure Functions registers the failure
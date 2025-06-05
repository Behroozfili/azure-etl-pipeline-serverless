import logging
import azure.functions as func
import os
import requests
import json
import time

# Environment variable configurations for Databricks and Azure Storage
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
DATABRICKS_JOB_ID_MODEL_TRAINING = os.environ.get("DATABRICKS_JOB_ID_MODEL_TRAINING")

STORAGE_ACCOUNT_NAME_PARAM = os.environ.get("STORAGE_ACCOUNT_NAME_PARAM")
DATASETS_CONTAINER_NAME_PARAM = os.environ.get("DATASETS_CONTAINER_NAME_PARAM")
MODELS_CONTAINER_NAME_PARAM = os.environ.get("MODELS_CONTAINER_NAME_PARAM")
AZURE_STORAGE_ACCOUNT_KEY_PARAM = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY_PARAM")  # Optional

def trigger_databricks_job(job_id: str, notebook_params: dict) -> dict:
    """Trigger a Databricks job and return the run ID or error details."""
    if not all([DATABRICKS_HOST, DATABRICKS_TOKEN, job_id]):
        msg = "Missing Databricks host, token, or job ID."
        logging.error(msg)
        return {"status": "error", "message": msg, "error_type": "ConfigurationError"}

    url = f"{DATABRICKS_HOST.rstrip('/')}/api/2.0/jobs/run-now"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"job_id": int(job_id)}
    if notebook_params:
        payload["notebook_params"] = notebook_params

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        run_id = response.json().get("run_id")
        logging.info(f"Triggered Databricks job. Run ID: {run_id}")
        return {"status": "submitted", "run_id": run_id, "job_id": job_id}
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error: {http_err} - {response.text}")
        return {"status": "error", "message": f"HTTP Error: {response.status_code} - {response.text}", "error_type": "HttpError"}
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request exception: {req_err}")
        return {"status": "error", "message": str(req_err), "error_type": "RequestError"}

def get_databricks_run_status(run_id: int) -> dict:
    """Poll Databricks for the job run status by run ID."""
    if not all([DATABRICKS_HOST, DATABRICKS_TOKEN]):
        msg = "Missing Databricks host or token."
        logging.error(msg)
        return {"status": "error", "message": msg, "error_type": "ConfigurationError"}

    url = f"{DATABRICKS_HOST.rstrip('/')}/api/2.1/jobs/runs/get?run_id={run_id}"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error while checking run status: {http_err} - {response.text}")
        return {"status": "error", "message": f"HTTP Error: {response.status_code} - {response.text}", "error_type": "HttpError"}
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request exception while checking run status: {req_err}")
        return {"status": "error", "message": str(req_err), "error_type": "RequestError"}

async def main(queueMsg: func.QueueMessage) -> None:
    logging.info(f"Processing queue message: {queueMsg.id}")
    try:
        message_body_str = queueMsg.get_body().decode('utf-8')
        logging.info(f"Message body: {message_body_str}")
    except Exception as e:
        logging.error(f"Failed to parse message body: {e}", exc_info=True)
        return

    if not DATABRICKS_JOB_ID_MODEL_TRAINING or not STORAGE_ACCOUNT_NAME_PARAM:
        logging.error("Missing required environment configuration.")
        return

    notebook_job_params = {
        "STORAGE_ACCOUNT_NAME": STORAGE_ACCOUNT_NAME_PARAM,
        "DATASETS_CONTAINER_NAME": DATASETS_CONTAINER_NAME_PARAM,
        "MODELS_CONTAINER_NAME": MODELS_CONTAINER_NAME_PARAM
    }
    if AZURE_STORAGE_ACCOUNT_KEY_PARAM:
        notebook_job_params["AZURE_STORAGE_ACCOUNT_KEY"] = AZURE_STORAGE_ACCOUNT_KEY_PARAM

    notebook_job_params = {k: v for k, v in notebook_job_params.items() if v}

    try:
        submission_response = trigger_databricks_job(DATABRICKS_JOB_ID_MODEL_TRAINING, notebook_job_params)
        if submission_response.get("status") == "error":
            logging.error(f"Job submission failed: {submission_response.get('message')}")
            return

        run_id = submission_response.get("run_id")
        if not run_id:
            logging.error("Databricks run_id not returned.")
            return

        max_wait_time_seconds = 1800
        poll_interval_seconds = 60
        start_time = time.time()
        final_status_details = None

        logging.info(f"Polling Databricks run status for run ID: {run_id}")
        while time.time() - start_time < max_wait_time_seconds:
            run_details = get_databricks_run_status(run_id)
            if run_details.get("status") == "error":
                logging.error(f"Polling error: {run_details.get('message')}")
                raise Exception(f"Polling error: {run_details.get('message')}")

            state_info = run_details.get("state", {})
            life_cycle_state = state_info.get("life_cycle_state", "UNKNOWN")
            logging.info(f"Run ID {run_id} state: {life_cycle_state}")

            if life_cycle_state in ["TERMINATED", "SKIPPED", "INTERNAL_ERROR"]:
                result_state = state_info.get("result_state", "UNKNOWN")
                state_message = state_info.get("state_message", "")
                job_output = None

                if result_state == "SUCCESS":
                    notebook_output_result_str = run_details.get("run_output", {}).get("notebook_output", {}).get("result")
                    try:
                        job_output = json.loads(notebook_output_result_str)
                    except (TypeError, json.JSONDecodeError):
                        job_output = {"raw_output": notebook_output_result_str}

                final_status_details = {
                    "run_id": run_id,
                    "job_id": DATABRICKS_JOB_ID_MODEL_TRAINING,
                    "life_cycle_state": life_cycle_state,
                    "result_state": result_state,
                    "state_message": state_message,
                    "notebook_output": job_output
                }
                logging.info(f"Job completed: {json.dumps(final_status_details)}")
                break

            time.sleep(poll_interval_seconds)
        else:
            final_status_details = {
                "run_id": run_id,
                "job_id": DATABRICKS_JOB_ID_MODEL_TRAINING,
                "life_cycle_state": "TIMED_OUT_WAITING",
                "result_state": "UNKNOWN",
                "state_message": f"Timed out after {max_wait_time_seconds} seconds."
            }
            logging.warning(f"Job polling timed out: {json.dumps(final_status_details)}")

        if final_status_details and final_status_details.get("result_state") != "SUCCESS":
            logging.error(f"Databricks job {run_id} failed: {final_status_details.get('result_state')}")
            # raise Exception(...) if retry is desired

    except ValueError as ve:
        logging.error(f"Configuration error: {ve}", exc_info=True)
    except requests.exceptions.RequestException as re:
        logging.error(f"Databricks API failure: {re}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        raise

    logging.info(f"Finished processing message: {queueMsg.id}")

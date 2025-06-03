# ./transform_function/tests/test_transform_logic.py
import pytest
import json
from unittest.mock import patch, MagicMock, ANY
import os

# Attempt to import the main function from __init__.py
# This might require adjusting PYTHONPATH if run from a different directory structure
# For simplicity, assume it's importable or adjust as needed.
# One common way is to ensure the 'transform_function' folder is in a place
# where Python's import machinery can find it, or by adding its parent to sys.path.
# For now, let's assume the test runner handles this or it's in the same package.
try:
    from transform_function import __init__ as transform_function_module
except ImportError:
    # Fallback for simpler test structures or if __init__.py is not directly importable as a module
    # This is a common issue depending on how tests are structured and run.
    # A better approach involves proper packaging or PYTHONPATH setup.
    import sys
    # Add the parent directory of 'transform_function' to the Python path
    # This assumes your tests are in 'transform_function/tests' and __init__.py is in 'transform_function'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    # Now try importing again. If this still fails, the test setup/structure needs review.
    # It's also common to have a top-level 'src' directory.
    # For this example, we'll assume __init__.py can be accessed.
    # A common pattern for Azure Functions testing is to treat the function file as a script.
    # However, for mocking, direct import is often cleaner if possible.
    # If direct import is problematic, consider refactoring __init__.py
    # to have its core logic in a separate, easily importable function.
    # For this example, we proceed as if 'transform_function_module.main' is accessible.
    from __init__ import main as main_function # Assuming __init__.py is in the same effective package path

# Mock for azure.functions.QueueMessage
class MockQueueMessage:
    def __init__(self, body_content):
        if isinstance(body_content, dict) or isinstance(body_content, list):
            self._body = json.dumps(body_content).encode('utf-8')
        else:
            self._body = str(body_content).encode('utf-8')

    def get_body(self):
        return self._body

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mocks necessary environment variables for the function."""
    monkeypatch.setenv("DATABRICKS_HOST", "https://mock.databricks.net")
    monkeypatch.setenv("DATABRICKS_TOKEN", "mock_token_value")
    monkeypatch.setenv("DATABRICKS_NOTEBOOK_PATH", "/Shared/mock_notebook_path")
    monkeypatch.setenv("RAW_DATA_CONTAINER_NAME", "mock-raw-container")
    monkeypatch.setenv("PROCESSED_DATA_CONTAINER_NAME", "mock-processed-container")
    monkeypatch.setenv("STORAGE_ACCOUNT_NAME", "mockstorageaccount")
    monkeypatch.setenv("DATABRICKS_NODE_TYPE_ID", "mock_node_type")
    monkeypatch.setenv("DATABRICKS_SPARK_VERSION", "mock_spark_version")
    monkeypatch.setenv("DATABRICKS_MIN_WORKERS", "0")
    monkeypatch.setenv("DATABRICKS_MAX_WORKERS", "0")
    monkeypatch.setenv("DATABRICKS_RUN_TIMEOUT_SECONDS", "60") # Short timeout for tests
    monkeypatch.setenv("LOAD_TRIGGER_QUEUE_NAME", "mock-load-queue-name")
    # A mock connection string for Azurite or similar local storage emulator
    monkeypatch.setenv("AzureWebJobsStorage", "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;")

# Patch the Databricks WorkspaceClient and Azure Storage QueueServiceClient
# The path to patch should be where the object is *looked up*, not where it's defined.
# If __init__.py imports WorkspaceClient as 'from databricks_sdk import WorkspaceClient',
# then you patch 'transform_function.__init__.WorkspaceClient'.
@patch('transform_function.__init__.WorkspaceClient')
@patch('transform_function.__init__.QueueServiceClient')
def test_transform_function_successful_run(MockQueueServiceClient, MockWorkspaceClient, mock_env_vars, caplog):
    """Tests the successful execution path of the transform function."""
    caplog.set_level(logging.INFO) # Capture info level logs

    # --- Mock Databricks SDK ---
    mock_databricks_ws_instance = MockWorkspaceClient.return_value
    mock_run_submission_response = MagicMock()
    mock_run_submission_response.run_id = "test-run-123"
    mock_run_submission_response.job_id = None # For submit_run, job_id might be None
    mock_databricks_ws_instance.jobs.submit_run.return_value = mock_run_submission_response

    mock_completed_run_info = MagicMock()
    # Configure the mock 'state' attribute, which itself needs 'life_cycle_state' and 'result_state'
    mock_completed_run_info.state = MagicMock()
    mock_completed_run_info.state.life_cycle_state = "TERMINATED"
    mock_completed_run_info.state.result_state = "SUCCESS"
    mock_databricks_ws_instance.jobs.wait_get_run_job_terminated_or_skipped.return_value = mock_completed_run_info

    # --- Mock Azure Storage Queue SDK ---
    mock_queue_service_client_instance = MockQueueServiceClient.from_connection_string.return_value
    mock_queue_client_instance = mock_queue_service_client_instance.get_queue_client.return_value

    # --- Prepare Input Message ---
    input_message_content = "olist_trigger_payload"
    mock_input_msg = MockQueueMessage(body_content=input_message_content)

    # --- Call the Main Function ---
    # Assuming 'main_function' is the 'main' from __init__.py
    main_function(mock_input_msg)


    # --- Assertions ---
    # Databricks job submission
    MockWorkspaceClient.assert_called_once_with(host="https://mock.databricks.net", token="mock_token_value")
    mock_databricks_ws_instance.jobs.submit_run.assert_called_once()
    # You can add more detailed assertions on the arguments passed to submit_run if needed
    # e.g., assert 'run_name' in mock_databricks_ws_instance.jobs.submit_run.call_args.kwargs

    # Databricks job completion wait
    mock_databricks_ws_instance.jobs.wait_get_run_job_terminated_or_skipped.assert_called_once_with("test-run-123")

    # Message sent to load queue
    MockQueueServiceClient.from_connection_string.assert_called_once_with(os.environ["AzureWebJobsStorage"])
    mock_queue_service_client_instance.get_queue_client.assert_called_once_with("mock-load-queue-name")
    mock_queue_client_instance.send_message.assert_called_once()
    # Check content of the message sent
    sent_message_arg = mock_queue_client_instance.send_message.call_args[0][0]
    sent_message_data = json.loads(sent_message_arg)
    assert sent_message_data["dataset_name"] == "olist_ecommerce"
    assert sent_message_data["status"] == "transformed_successfully"

    # Check log messages
    assert "Databricks run submitted. Run ID: test-run-123" in caplog.text
    assert "Databricks notebook run test-run-123 completed successfully." in caplog.text
    assert "Message sent to 'mock-load-queue-name'." in caplog.text

@patch('transform_function.__init__.WorkspaceClient')
@patch('transform_function.__init__.QueueServiceClient') # Patch even if not used in failure path for consistency
def test_transform_function_databricks_job_failure(MockQueueServiceClient, MockWorkspaceClient, mock_env_vars, caplog):
    """Tests the scenario where the Databricks job fails."""
    caplog.set_level(logging.INFO)

    # Mock Databricks SDK for failure
    mock_databricks_ws_instance = MockWorkspaceClient.return_value
    mock_run_submission_response = MagicMock()
    mock_run_submission_response.run_id = "test-run-fail-456"
    mock_run_submission_response.job_id = None
    mock_databricks_ws_instance.jobs.submit_run.return_value = mock_run_submission_response

    mock_failed_run_info = MagicMock()
    mock_failed_run_info.state = MagicMock()
    mock_failed_run_info.state.life_cycle_state = "TERMINATED"
    mock_failed_run_info.state.result_state = "FAILED"
    mock_failed_run_info.state.state_message = "Notebook execution error: Something went wrong."
    mock_databricks_ws_instance.jobs.wait_get_run_job_terminated_or_skipped.return_value = mock_failed_run_info

    input_message_content = "olist_failure_trigger"
    mock_input_msg = MockQueueMessage(body_content=input_message_content)

    # Expect an exception to be raised
    with pytest.raises(Exception) as exc_info:
        main_function(mock_input_msg)

    # Assertions for failure
    assert "Databricks notebook run test-run-fail-456 failed" in str(exc_info.value)
    assert "Notebook execution error: Something went wrong." in str(exc_info.value)

    # Check that no message was sent to the load queue
    mock_queue_service_client_instance = MockQueueServiceClient.from_connection_string.return_value
    mock_queue_client_instance = mock_queue_service_client_instance.get_queue_client.return_value
    mock_queue_client_instance.send_message.assert_not_called()

    # Check log messages
    assert "Databricks run submitted. Run ID: test-run-fail-456" in caplog.text
    assert "Databricks notebook run test-run-fail-456 failed" in caplog.text
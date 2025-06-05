# ./transform_function/tests/test_transform_logic.py
import pytest
import json
from unittest.mock import patch, MagicMock
import os
import logging

# Import the main function from the transform_function package
try:
    from transform_function import __init__ as transform_function_module
    main_function = transform_function_module.main
except ImportError:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from __init__ import main as main_function

# Mock class to simulate Azure QueueMessage
class MockQueueMessage:
    def __init__(self, body_content):
        if isinstance(body_content, (dict, list)):
            self._body = json.dumps(body_content).encode('utf-8')
        else:
            self._body = str(body_content).encode('utf-8')

    def get_body(self):
        return self._body

@pytest.fixture
def mock_env_vars(monkeypatch):
    # Set environment variables needed by the function
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
    monkeypatch.setenv("DATABRICKS_RUN_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("LOAD_TRIGGER_QUEUE_NAME", "mock-load-queue-name")
    monkeypatch.setenv("AzureWebJobsStorage", "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;")

@patch('transform_function.__init__.WorkspaceClient')
@patch('transform_function.__init__.QueueServiceClient')
def test_transform_function_successful_run(MockQueueServiceClient, MockWorkspaceClient, mock_env_vars, caplog):
    caplog.set_level(logging.INFO)

    # Mock Databricks WorkspaceClient and its job submission
    mock_databricks_ws_instance = MockWorkspaceClient.return_value
    mock_run_submission_response = MagicMock()
    mock_run_submission_response.run_id = "test-run-123"
    mock_run_submission_response.job_id = None
    mock_databricks_ws_instance.jobs.submit_run.return_value = mock_run_submission_response

    # Mock successful job completion state
    mock_completed_run_info = MagicMock()
    mock_completed_run_info.state = MagicMock()
    mock_completed_run_info.state.life_cycle_state = "TERMINATED"
    mock_completed_run_info.state.result_state = "SUCCESS"
    mock_databricks_ws_instance.jobs.wait_get_run_job_terminated_or_skipped.return_value = mock_completed_run_info

    # Mock Azure Storage QueueServiceClient and QueueClient
    mock_queue_service_client_instance = MockQueueServiceClient.from_connection_string.return_value
    mock_queue_client_instance = mock_queue_service_client_instance.get_queue_client.return_value

    # Prepare input message for the function
    input_message_content = "olist_trigger_payload"
    mock_input_msg = MockQueueMessage(body_content=input_message_content)

    # Call the function under test
    main_function(mock_input_msg)

    # Verify Databricks job submission was called correctly
    MockWorkspaceClient.assert_called_once_with(host="https://mock.databricks.net", token="mock_token_value")
    mock_databricks_ws_instance.jobs.submit_run.assert_called_once()
    mock_databricks_ws_instance.jobs.wait_get_run_job_terminated_or_skipped.assert_called_once_with("test-run-123")

    # Verify message was sent to Azure queue
    MockQueueServiceClient.from_connection_string.assert_called_once_with(os.environ["AzureWebJobsStorage"])
    mock_queue_service_client_instance.get_queue_client.assert_called_once_with("mock-load-queue-name")
    mock_queue_client_instance.send_message.assert_called_once()

    sent_message_arg = mock_queue_client_instance.send_message.call_args[0][0]
    sent_message_data = json.loads(sent_message_arg)
    assert sent_message_data["dataset_name"] == "olist_ecommerce"
    assert sent_message_data["status"] == "transformed_successfully"

    # Check for expected log messages
    assert "Databricks run submitted. Run ID: test-run-123" in caplog.text
    assert "Databricks notebook run test-run-123 completed successfully." in caplog.text
    assert "Message sent to 'mock-load-queue-name'." in caplog.text

@patch('transform_function.__init__.WorkspaceClient')
@patch('transform_function.__init__.QueueServiceClient')
def test_transform_function_databricks_job_failure(MockQueueServiceClient, MockWorkspaceClient, mock_env_vars, caplog):
    caplog.set_level(logging.INFO)

    # Mock Databricks job submission with a run ID
    mock_databricks_ws_instance = MockWorkspaceClient.return_value
    mock_run_submission_response = MagicMock()
    mock_run_submission_response.run_id = "test-run-fail-456"
    mock_run_submission_response.job_id = None
    mock_databricks_ws_instance.jobs.submit_run.return_value = mock_run_submission_response

    # Mock a failed job state with an error message
    mock_failed_run_info = MagicMock()
    mock_failed_run_info.state = MagicMock()
    mock_failed_run_info.state.life_cycle_state = "TERMINATED"
    mock_failed_run_info.state.result_state = "FAILED"
    mock_failed_run_info.state.state_message = "Notebook execution error: Something went wrong."
    mock_databricks_ws_instance.jobs.wait_get_run_job_terminated_or_skipped.return_value = mock_failed_run_info

    input_message_content = "olist_failure_trigger"
    mock_input_msg = MockQueueMessage(body_content=input_message_content)

    # Expect function to raise Exception on failure
    with pytest.raises(Exception) as exc_info:
        main_function(mock_input_msg)

    # Verify exception message content
    assert "Databricks notebook run test-run-fail-456 failed" in str(exc_info.value)
    assert "Notebook execution error: Something went wrong." in str(exc_info.value)

    # Verify no message was sent to the load queue on failure
    mock_queue_service_client_instance = MockQueueServiceClient.from_connection_string.return_value
    mock_queue_client_instance = mock_queue_service_client_instance.get_queue_client.return_value
    mock_queue_client_instance.send_message.assert_not_called()

    # Check for expected log messages on failure
    assert "Databricks run submitted. Run ID: test-run-fail-456" in caplog.text
    assert "Databricks notebook run test-run-fail-456 failed" in caplog.text

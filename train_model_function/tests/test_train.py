import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import pytest
import asyncio
from azure.functions import QueueMessage
import requests

# Import the module under test (assuming it's saved as databricks_function.py)
# from databricks_function import main, trigger_databricks_job, get_databricks_run_status


class TestDatabricksFunction(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.sample_queue_message_body = json.dumps({
            "dataset_id": "test_dataset",
            "model_type": "classification"
        })
        
        self.mock_env_vars = {
            "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
            "DATABRICKS_TOKEN": "test_token_123",
            "DATABRICKS_JOB_ID_MODEL_TRAINING": "12345",
            "STORAGE_ACCOUNT_NAME_PARAM": "teststorage",
            "DATASETS_CONTAINER_NAME_PARAM": "datasets",
            "MODELS_CONTAINER_NAME_PARAM": "models",
            "AZURE_STORAGE_ACCOUNT_KEY_PARAM": "test_key"
        }

    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123"
    })
    @patch('requests.post')
    def test_trigger_databricks_job_success(self, mock_post):
        """Test successful Databricks job triggering."""
        from databricks_function import trigger_databricks_job
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"run_id": 67890}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = trigger_databricks_job("12345", {"param1": "value1"})
        
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["run_id"], 67890)
        self.assertEqual(result["job_id"], "12345")
        
        # Verify the API call was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("Authorization", call_args[1]["headers"])
        self.assertEqual(call_args[1]["json"]["job_id"], 12345)

    @patch.dict('os.environ', {})
    def test_trigger_databricks_job_missing_config(self):
        """Test error handling when configuration is missing."""
        from databricks_function import trigger_databricks_job
        
        result = trigger_databricks_job("12345", {})
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "ConfigurationError")
        self.assertIn("Missing Databricks", result["message"])

    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123"
    })
    @patch('requests.post')
    def test_trigger_databricks_job_http_error(self, mock_post):
        """Test HTTP error handling."""
        from databricks_function import trigger_databricks_job
        
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_post.return_value = mock_response
        
        result = trigger_databricks_job("12345", {})
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "HttpError")
        self.assertIn("401", result["message"])

    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123"
    })
    @patch('requests.get')
    def test_get_databricks_run_status_success(self, mock_get):
        """Test successful run status retrieval."""
        from databricks_function import get_databricks_run_status
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "state": {
                "life_cycle_state": "RUNNING",
                "result_state": None
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = get_databricks_run_status(67890)
        
        self.assertEqual(result["state"]["life_cycle_state"], "RUNNING")
        mock_get.assert_called_once()

    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123",
        "DATABRICKS_JOB_ID_MODEL_TRAINING": "12345",
        "STORAGE_ACCOUNT_NAME_PARAM": "teststorage",
        "DATASETS_CONTAINER_NAME_PARAM": "datasets",
        "MODELS_CONTAINER_NAME_PARAM": "models"
    })
    @patch('databricks_function.trigger_databricks_job')
    @patch('databricks_function.get_databricks_run_status')
    @patch('time.sleep')  # Mock sleep to speed up tests
    async def test_main_function_success(self, mock_sleep, mock_get_status, mock_trigger):
        """Test the main function with successful job completion."""
        from databricks_function import main
        
        # Mock queue message
        mock_queue_msg = Mock(spec=QueueMessage)
        mock_queue_msg.id = "test_message_id"
        mock_queue_msg.get_body.return_value = self.sample_queue_message_body.encode('utf-8')
        
        # Mock successful job submission
        mock_trigger.return_value = {
            "status": "submitted",
            "run_id": 67890,
            "job_id": "12345"
        }
        
        # Mock job completion
        mock_get_status.return_value = {
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "SUCCESS",
                "state_message": "Job completed successfully"
            },
            "run_output": {
                "notebook_output": {
                    "result": '{"model_accuracy": 0.95}'
                }
            }
        }
        
        # Run the main function
        await main(mock_queue_msg)
        
        # Verify job was triggered
        mock_trigger.assert_called_once()
        trigger_args = mock_trigger.call_args[0]
        self.assertEqual(trigger_args[0], "12345")  # job_id
        
        # Verify status was checked
        mock_get_status.assert_called()

    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123",
        "DATABRICKS_JOB_ID_MODEL_TRAINING": "12345",
        "STORAGE_ACCOUNT_NAME_PARAM": "teststorage"
    })
    @patch('databricks_function.trigger_databricks_job')
    async def test_main_function_job_submission_failure(self, mock_trigger):
        """Test main function when job submission fails."""
        from databricks_function import main
        
        # Mock queue message
        mock_queue_msg = Mock(spec=QueueMessage)
        mock_queue_msg.id = "test_message_id"
        mock_queue_msg.get_body.return_value = self.sample_queue_message_body.encode('utf-8')
        
        # Mock failed job submission
        mock_trigger.return_value = {
            "status": "error",
            "message": "Job submission failed",
            "error_type": "HttpError"
        }
        
        # Run the main function - should not raise exception
        await main(mock_queue_msg)
        
        # Verify job submission was attempted
        mock_trigger.assert_called_once()

    @patch.dict('os.environ', {})
    async def test_main_function_missing_config(self):
        """Test main function with missing configuration."""
        from databricks_function import main
        
        # Mock queue message
        mock_queue_msg = Mock(spec=QueueMessage)
        mock_queue_msg.id = "test_message_id"
        mock_queue_msg.get_body.return_value = self.sample_queue_message_body.encode('utf-8')
        
        # Run the main function - should return early due to missing config
        await main(mock_queue_msg)
        
        # Function should complete without errors due to early return

    async def test_main_function_invalid_message_body(self):
        """Test main function with invalid message body."""
        from databricks_function import main
        
        # Mock queue message with invalid body
        mock_queue_msg = Mock(spec=QueueMessage)
        mock_queue_msg.id = "test_message_id"
        mock_queue_msg.get_body.side_effect = Exception("Invalid message body")
        
        # Run the main function - should handle exception gracefully
        await main(mock_queue_msg)

    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123",
        "DATABRICKS_JOB_ID_MODEL_TRAINING": "12345",
        "STORAGE_ACCOUNT_NAME_PARAM": "teststorage"
    })
    @patch('databricks_function.trigger_databricks_job')
    @patch('databricks_function.get_databricks_run_status')
    @patch('time.sleep')
    @patch('time.time')
    async def test_main_function_job_timeout(self, mock_time, mock_sleep, mock_get_status, mock_trigger):
        """Test main function when job times out."""
        from databricks_function import main
        
        # Mock queue message
        mock_queue_msg = Mock(spec=QueueMessage)
        mock_queue_msg.id = "test_message_id"
        mock_queue_msg.get_body.return_value = self.sample_queue_message_body.encode('utf-8')
        
        # Mock successful job submission
        mock_trigger.return_value = {
            "status": "submitted",
            "run_id": 67890,
            "job_id": "12345"
        }
        
        # Mock time progression to simulate timeout
        mock_time.side_effect = [0, 1900]  # Start time, then past timeout
        
        # Mock job still running
        mock_get_status.return_value = {
            "state": {
                "life_cycle_state": "RUNNING",
                "result_state": None
            }
        }
        
        # Run the main function
        await main(mock_queue_msg)
        
        # Verify timeout was handled
        mock_trigger.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Integration tests that test multiple components together."""
    
    @patch.dict('os.environ', {
        "DATABRICKS_HOST": "https://test-databricks.azuredatabricks.net",
        "DATABRICKS_TOKEN": "test_token_123",
        "DATABRICKS_JOB_ID_MODEL_TRAINING": "12345",
        "STORAGE_ACCOUNT_NAME_PARAM": "teststorage",
        "DATASETS_CONTAINER_NAME_PARAM": "datasets",
        "MODELS_CONTAINER_NAME_PARAM": "models"
    })
    @patch('requests.post')
    @patch('requests.get')
    @patch('time.sleep')
    async def test_end_to_end_workflow(self, mock_sleep, mock_get, mock_post):
        """Test the complete workflow from message to job completion."""
        from databricks_function import main
        
        # Mock queue message
        mock_queue_msg = Mock(spec=QueueMessage)
        mock_queue_msg.id = "integration_test_message"
        mock_queue_msg.get_body.return_value = json.dumps({
            "dataset": "test_data.csv"
        }).encode('utf-8')
        
        # Mock job submission response
        mock_post_response = Mock()
        mock_post_response.json.return_value = {"run_id": 99999}
        mock_post_response.raise_for_status.return_value = None
        mock_post.return_value = mock_post_response
        
        # Mock job status response (completed successfully)
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "SUCCESS",
                "state_message": "Integration test completed"
            },
            "run_output": {
                "notebook_output": {
                    "result": '{"test": "passed", "accuracy": 0.98}'
                }
            }
        }
        mock_get_response.raise_for_status.return_value = None
        mock_get.return_value = mock_get_response
        
        # Execute the workflow
        await main(mock_queue_msg)
        
        # Verify the complete flow
        mock_post.assert_called_once()  # Job was submitted
        mock_get.assert_called()  # Status was checked
        
        # Verify API calls were made with correct parameters
        post_call_args = mock_post.call_args
        self.assertIn("job_id", post_call_args[1]["json"])
        self.assertEqual(post_call_args[1]["json"]["job_id"], 12345)


if __name__ == '__main__':
    # Run async tests
    async def run_async_tests():
        test_cases = [
            TestDatabricksFunction(),
            TestIntegration()
        ]
        
        for test_case in test_cases:
            for method_name in dir(test_case):
                if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_case, method_name)):
                    print(f"Running {test_case.__class__.__name__}.{method_name}")
                    await getattr(test_case, method_name)()
    
    # Run synchronous tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run asynchronous tests
    asyncio.run(run_async_tests())
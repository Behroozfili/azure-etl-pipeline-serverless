import unittest
from unittest.mock import MagicMock, patch
import azure.functions as func

from ..__init__ import main

class TestExtractFunction(unittest.TestCase):

    @patch.dict('os.environ', {
        "DATASETS_CONTAINER_NAME": "test-datasets",
        "RAW_DATA_CONTAINER_NAME": "test-raw-data",
        "TRANSFORM_QUEUE_NAME": "test-transform-queue"
    })
    def test_successful_extraction_and_queue_message(self):
        mock_input_blob = MagicMock(spec=func.InputStream)
        mock_input_blob.name = "test-datasets/sample.csv"
        mock_input_blob.length = 123
        mock_input_blob.read.return_value = b"col1,col2\nval1,val2"

        mock_output_blob = MagicMock(spec=func.Out)
        mock_output_queue_item = MagicMock(spec=func.Out)

        main(
            inputBlob=mock_input_blob,
            outputBlob=mock_output_blob,
            outputQueueItem=mock_output_queue_item
        )

        mock_input_blob.read.assert_called_once()
        mock_output_blob.set.assert_called_once_with(b"col1,col2\nval1,val2")
        mock_output_queue_item.set.assert_called_once_with("test-raw-data/sample.csv")

    @patch.dict('os.environ', {
        "DATASETS_CONTAINER_NAME": "test-datasets",
        "RAW_DATA_CONTAINER_NAME": "test-raw-data",
        "TRANSFORM_QUEUE_NAME": "test-transform-queue"
    })
    @patch('08.extract_function.__init__.logging')
    def test_exception_during_processing(self, mock_logging):
        mock_input_blob = MagicMock(spec=func.InputStream)
        mock_input_blob.name = "test-datasets/error.csv"
        mock_input_blob.read.side_effect = Exception("Simulated read error")

        mock_output_blob = MagicMock(spec=func.Out)
        mock_output_queue_item = MagicMock(spec=func.Out)

        with self.assertRaises(Exception) as context:
            main(
                inputBlob=mock_input_blob,
                outputBlob=mock_output_blob,
                outputQueueItem=mock_output_queue_item
            )

        self.assertTrue("Simulated read error" in str(context.exception))
        mock_logging.error.assert_called_once()

if __name__ == '__main__':
    unittest.main()

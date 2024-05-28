# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/prebid_server/efs_cleanup_lambda/delete_efs_files.py.
# USAGE:
#   ./run-unit-tests.sh --test-file-name prebid_server/test_delete_efs_files.py
###############################################################################

import os

from unittest.mock import patch

LOGS_TASK_ARN = "arn:aws:sync:us-west-2:9111122223333:task/task-example1"
METRICS_TASK_ARN = "arn:aws:sync:us-west-2:9111122223333:task/task-example2"

test_environ = {
    "EFS_MOUNT_PATH": "mnt/efs",
    "LOGS_TASK_ARN": LOGS_TASK_ARN,
    "METRICS_TASK_ARN": METRICS_TASK_ARN,
    "DATASYNC_REPORT_BUCKET": "test-report-bucket",
    "AWS_ACCOUNT_ID": "9111122223333",
    "METRICS_NAMESPACE": "test-namespace",
    "RESOURCE_PREFIX": "test-prefix",
    "EFS_METRICS" : "metrics",
    "EFS_LOGS" : "logs",
    "SOLUTION_VERSION" : "v1.9.99",
    "SOLUTION_ID" : "SO000123",
}

@patch.dict(os.environ, test_environ, clear=True)
@patch('aws_lambda_layers.metrics_layer.python.cloudwatch_metrics.metrics.Metrics.put_metrics_count_value_1')
@patch('aws_lambda_layers.datasync_s3_layer.python.datasync_reports.reports.get_transferred_object_keys')
@patch('os.remove')
@patch('aws_lambda_powertools.Logger.info')
@patch('aws_lambda_powertools.Logger.error')
def test_event_handler(
    mock_error, 
    mock_info, 
    mock_os_remove, 
    mock_get_transferred_object_keys,
    mock_metrics, 
    ):
    from prebid_server.efs_cleanup_lambda.delete_efs_files import event_handler

    mock_metrics.return_value = None

    # test log arn mapping with successful file processing
    mock_get_transferred_object_keys.return_value = ["key1", "key2"]
    test_event_1 = {
        "resources": [f"{LOGS_TASK_ARN}/execution/exec-example316440271f"]
    }
    event_handler(test_event_1, None)
    mock_info.assert_any_call("2 new logs files to process: ['key1', 'key2']")

    # test metric arn mapping with no file processing
    mock_get_transferred_object_keys.return_value = []
    test_event_2 = {
        "resources": [f"{METRICS_TASK_ARN}/execution/exec-example316440271f"]
    }
    event_handler(test_event_2, None)
    mock_info.assert_any_call("No new metrics files to delete from EFS.")

    # test unsuccessful file deletion
    mock_get_transferred_object_keys.return_value = ["key1", "key2"]
    mock_os_remove.side_effect = OSError()
    test_event_3 = {
        "resources": [f"{METRICS_TASK_ARN}/execution/exec-example316440271f"]
    }
    event_handler(test_event_3, None)
    mock_error.assert_any_call("2 files failed to delete: ['key1', 'key2']")

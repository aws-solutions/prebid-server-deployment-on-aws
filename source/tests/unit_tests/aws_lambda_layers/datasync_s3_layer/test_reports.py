# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/aws_lambda_layers/datasync_s3_layer/datasync_reports/reports.py
# USAGE:
#   ./run-unit-tests.sh --test-file-name aws_lambda_layers/datasync_s3_layer/test_reports.py
###############################################################################

import json

import pytest
from unittest.mock import patch

def test_get_verified_files():
    from aws_lambda_layers.datasync_s3_layer.python.datasync_reports.reports import get_verified_files

    # test parsing of DataSync file names
    test_files_1 = [
        {
            "Key": "task-id.execution_id-verified-12345"
        },
        {
            "Key": "task-id.execution_id-failed-12345"
        }
    ]
    keys = get_verified_files(files=test_files_1)
    assert keys == ["task-id.execution_id-verified-12345"]

    # test error raising when no verified files found
    test_files_2 = [
        {
            "Key": "task-id.execution_id-failed-12345"
        }
    ]
    with pytest.raises(ValueError):
        get_verified_files(files=test_files_2)


@patch('boto3.client')
def test_get_transferred_object_keys(
    mock_boto3     
):
    from aws_lambda_layers.datasync_s3_layer.python.datasync_reports.reports import get_transferred_object_keys

    mock_boto3.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "task-id.execution_id-verified-12345"
            },
            {
                "Key": "task-id.execution_id-failed-12345"
            }
        ]
    }
    mock_boto3.get_object.return_value = {
        "Body": {"read": lambda: json.dumps({"Verified": [{"RelativePath": "file.txt", "VerifyStatus": "SUCCESS", "DstMetadata": {"Type": "File"}}]})}
    }

    test_event = {
        "resources": ["arn:aws:sync:us-west-2:9111122223333:task/task-example2/execution/exec-example316440271f"]
    }
    test_datasync_bucket = "test-bucket"
    test_aws_account = "9111122223333"

    get_transferred_object_keys(
        event=test_event,
        datasync_report_bucket=test_datasync_bucket,
        aws_account_id=test_aws_account,
        s3_client=mock_boto3
    )
    mock_boto3.list_objects_v2.assert_called_once_with(
        Bucket=test_datasync_bucket,
        Prefix="datasync/Detailed-Reports/task-example2/exec-example316440271f/",
        ExpectedBucketOwner=test_aws_account
    )
    mock_boto3.get_object.assert_called_once_with(
        Bucket=test_datasync_bucket,
        Key="task-id.execution_id-verified-12345",
        ExpectedBucketOwner=test_aws_account
    )

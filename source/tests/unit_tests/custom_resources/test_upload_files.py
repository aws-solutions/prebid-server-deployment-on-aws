# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/custom_resources/artifacts_bucket_lambda/upload_files.py
# USAGE:
#   ./run-unit-tests.sh --test-file-name custom_resources/test_upload_files.py
###############################################################################


from unittest.mock import patch, call


@patch("crhelper.CfnResource")
@patch("custom_resources.artifacts_bucket_lambda.upload_files.helper")
def test_event_handler(helper_mock, _):
    from custom_resources.artifacts_bucket_lambda.upload_files import event_handler

    event_handler({}, None)
    helper_mock.assert_called_once()

@patch("crhelper.CfnResource")
@patch("custom_resources.artifacts_bucket_lambda.upload_files.upload_file")
def test_on_create_or_update(mock_upload_file, _):
    from custom_resources.artifacts_bucket_lambda.upload_files import on_create_or_update

    test_event = {
        "ResourceProperties": {
            "test_key" : "test_value"
            }
        }
    
    on_create_or_update(test_event, None)
    mock_upload_file.assert_called_once_with(
        {"test_key": "test_value"}
    )

@patch("crhelper.CfnResource")
@patch("custom_resources.artifacts_bucket_lambda.upload_files.s3_client")
@patch("custom_resources.artifacts_bucket_lambda.upload_files.os.walk")
@patch("custom_resources.artifacts_bucket_lambda.upload_files.os.listdir")
def test_upload_file(mock_listdir, mock_walk, mock_s3_client, _):
    from custom_resources.artifacts_bucket_lambda.upload_files import upload_file

    mock_walk.return_value = [("/some/root", ["dir1", "dir2"], [])]
    mock_listdir.return_value = ["file1.txt", "file2.txt"]

    test_properties = {
        "artifacts_bucket_name": "test_bucket"
    }
    upload_file(resource_properties=test_properties)

    mock_s3_client.upload_file.assert_has_calls([
        call('/some/root/dir1/file1.txt', 'test_bucket', 'dir1/file1.txt'),
        call('/some/root/dir1/file2.txt', 'test_bucket', 'dir1/file2.txt'),
        call('/some/root/dir2/file1.txt', 'test_bucket', 'dir2/file1.txt'),
        call('/some/root/dir2/file2.txt', 'test_bucket', 'dir2/file2.txt')
    ])

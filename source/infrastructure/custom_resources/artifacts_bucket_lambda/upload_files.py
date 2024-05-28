# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
This module is a custom resource Lambda for uploading files to the solution artifacts S3 bucket.
Any files placed in the artifacts_bucket_lambda/files directory will uploaded to S3 under the same directory prefix.

Example: files/glue/metrics_glue_script.py is uploaded to the artifacts bucket with the object key: {bucket=name}/glue/metrics_glue_script.py
"""

import os

from crhelper import CfnResource
from aws_lambda_powertools import Logger
import boto3

FILE_DIR = "files"

logger = Logger(service="artifacts-bucket-upload-lambda", level="INFO")
helper = CfnResource(log_level="ERROR", boto_level="ERROR")
s3_client = boto3.client("s3")


def event_handler(event, context):
    """
    This is the Lambda custom resource entry point.
    """

    logger.info(event)
    helper(event, context)


@helper.create
@helper.update
def on_create_or_update(event, _) -> None:
    resource_properties = event["ResourceProperties"]
    try:
        response = upload_file(resource_properties)
    except Exception as err:
        logger.error(err)
        raise err

    helper.Data.update({"Response": response})


def upload_file(resource_properties) -> list:
    """
    This function handles uploading files to the S3 artifacts bucket
    """
    artifacts_bucket_name = resource_properties["artifacts_bucket_name"]

    success = []
    for root, dirs, _ in os.walk(FILE_DIR):
        for subdir in dirs:
            subdir_path = os.path.join(root, subdir)
            for artifact_file in os.listdir(subdir_path):
                local_obj_path = os.path.join(subdir_path, artifact_file)
                object_key = f"{subdir}/{artifact_file}"

                if artifact_file == "__pycache__":
                    logger.info(f"Encountered pycache {object_key} while uploading")
                    continue

                s3_client.upload_file(local_obj_path, artifacts_bucket_name, object_key)
                success_message = f"Uploaded {object_key}"
                logger.info(success_message)

    return success

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json

from aws_lambda_powertools import Logger

logger = Logger(utc=True, service="efs-cleanup-lambda")

def get_verified_files(files: list) -> list:
    """
    Function to retrieve DataSync verified report files from S3.
    """
    # DataSync can write multiple reports depending on the result of the transfer such as:
    #    - exec-0a12a34ab112233ab.files-verified-v1-00001-0a123abc12d3b0e4f.json
    #    - exec-0a12a34ab112233ab.files-transferred-v1-00001-0a123abc12d3b0e4f.json
    # We split and parse the file name to ensure the file is a verified report before returning the file key back.

    keys = []
    for file in files:
        key = file["Key"]
        key_parts = key.split(".")
        report = key_parts[1]
        report_parts = report.split("-")
        report_type = report_parts[1]
        if report_type == "verified":
            keys.append(key)

    if len(keys) == 0:
        raise ValueError("Verified report files not found.")
        
    return keys
    
def get_transferred_object_keys(event: dict, datasync_report_bucket: str, aws_account_id: str, s3_client) -> list:
    """
    Function to parse DataSync reports in S3 and return successfully transferred object keys.
    """
    
    object_keys = []
    try:
        event_parts = event['resources'][0].split('/')
        task_id = event_parts[1]
        execution_id = event_parts[3]
        report_key_prefix = f"datasync/Detailed-Reports/{task_id}/{execution_id}/"
        
        response = s3_client.list_objects_v2(
            Bucket=datasync_report_bucket,
            Prefix=report_key_prefix,
            ExpectedBucketOwner=aws_account_id
        )
        report_files = response["Contents"]
        
        skipped_files = []
        verified_keys = get_verified_files(files=report_files)
        for key in verified_keys:
            response = s3_client.get_object(
                Bucket=datasync_report_bucket,
                Key=key,
                ExpectedBucketOwner=aws_account_id
            )
            content = response["Body"].read().decode("utf-8")
            json_content = json.loads(content)
    
            verified_transfers = json_content["Verified"]
            for transfer in verified_transfers:
                key = transfer["RelativePath"]
                if transfer['DstMetadata']['Type'] == "Directory":
                    continue
                if transfer["VerifyStatus"] != "SUCCESS":
                    skipped_files.append(key)
                    continue
                object_keys.append(key)

        if len(skipped_files) > 0:
            # The next time DataSync runs, the file will attempt transfer again and overwrite the previous version in S3
            logger.info(f"Transfer validation not successful for skipped files: {skipped_files}. Check CloudWatch logs for task execution: {execution_id}.")

    except Exception as e:
        logger.error(f"Error getting DataSync report: {e}")
    
    return object_keys
    
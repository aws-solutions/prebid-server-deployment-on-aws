# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
This module is a custom lambda for getting the prefix list id for the ALB security group
"""

import boto3
from aws_lambda_powertools import Logger
from crhelper import CfnResource


logger = Logger(utc=True, service="prefix-id-custom-lambda")
helper = CfnResource(log_level="ERROR", boto_level="ERROR")


def event_handler(event, context):
    """
    This is the Lambda custom resource entry point.
    """
    logger.info(event)
    helper(event, context)


@helper.create
def on_create(event, _) -> None:
    """
    Function to get prefix_list_id from prefix_list_name
    """
    prefix_list_name = "com.amazonaws.global.cloudfront.origin-facing"

    ec2_client = boto3.client("ec2")
    response = ec2_client.describe_managed_prefix_lists()
    prefix_list_id = None

    try:
        prefix_list_id = next(
            prefix_list["PrefixListId"]
            for prefix_list in response["PrefixLists"]
            if prefix_list["PrefixListName"] == prefix_list_name
        )
    except StopIteration as exception:
        logger.error(exception)
        raise exception

    helper.Data.update({"prefix_list_id": prefix_list_id})

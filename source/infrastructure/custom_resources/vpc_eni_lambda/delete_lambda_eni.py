# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
This module is a custom lambda for deleting VPC ENIs for the Lambda service
"""

import boto3
from aws_lambda_powertools import Logger
from crhelper import CfnResource

logger = Logger(utc=True, service="vpc-eni-lambda")
helper = CfnResource(log_level="ERROR", boto_level="ERROR")


def event_handler(event, context):
    """
    This is the Lambda custom resource entry point.
    """
    logger.info(event)
    helper(event, context)


@helper.delete
def on_delete(event, _) -> None:
    """
    Function to delete Lambda service VPC ENIs
    """
    SECURITY_GROUP_ID = event["ResourceProperties"]["SECURITY_GROUP_ID"]

    ec2_client = boto3.client("ec2")

    desribe_response = ec2_client.describe_network_interfaces(
        Filters=[{"Name": "group-id", "Values": [SECURITY_GROUP_ID]}]
    )
    return_responses = []
    for network_interface in desribe_response["NetworkInterfaces"]:
        try:
            attachment_id = network_interface["Attachment"]["AttachmentId"]
            ec2_client.detach_network_interface(AttachmentId=attachment_id)

            logger.info(f"Detached ENI: {attachment_id}")

        except Exception as e:
            logger.exception(e)

        try:
            network_id = network_interface["NetworkInterfaceId"]
            response = ec2_client.delete_network_interface(
                NetworkInterfaceId=network_id
            )

            return_responses.append(response)

            logger.info(f"Deleted ENI: {network_id}")

        except Exception as e:
            logger.exception(e)

    helper.Data.update({"Response": return_responses})

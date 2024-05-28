# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
This module is a custom lambda for enabling access logs for ALB
"""

import boto3
from aws_lambda_powertools import Logger
from crhelper import CfnResource


logger = Logger(utc=True, service="alb-access-log-lambda")
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
    Function to enable access logging for ALB
    """

    elbv2_client = boto3.client("elbv2")

    alb_arn = event["ResourceProperties"]["ALB_ARN"]
    access_log_bucket = event["ResourceProperties"]["ALB_LOG_BUCKET"]

    response = elbv2_client.modify_load_balancer_attributes(
        LoadBalancerArn=alb_arn,
        Attributes=[
            {"Key": "access_logs.s3.enabled", "Value": "true"},
            {"Key": "access_logs.s3.bucket", "Value": access_log_bucket},
        ],
    )

    logger.info(response)

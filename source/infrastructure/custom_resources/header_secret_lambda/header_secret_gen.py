# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
This module is a custom lambda for producing a secret value for CloudFront header
"""

import secrets
from aws_lambda_powertools import Logger
from crhelper import CfnResource


logger = Logger(utc=True, service="header-secret-custom-lambda")
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
    Function to produce a secret value for CloudFront header
    """
    helper.Data.update({"header_secret_value": secrets.token_urlsafe(16)})

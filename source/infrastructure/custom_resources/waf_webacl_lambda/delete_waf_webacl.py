# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
This module is a custom lambda for deletion of Waf Web ACL and associations
"""

import boto3
import os
from botocore import config
from aws_lambda_powertools import Logger
from crhelper import CfnResource

logger = Logger(utc=True, service="waf-custom-lambda")
helper = CfnResource(log_level="ERROR", boto_level="ERROR")

SOLUTION_ID = os.environ["SOLUTION_ID"]
SOLUTION_VERSION = os.environ["SOLUTION_VERSION"]

def event_handler(event, context):
    """
    This is the Lambda custom resource entry point.
    """

    logger.info(event)
    helper(event, context)


@helper.delete
def on_delete(event, _):
    # Add the solution identifier to boto3 requests for attributing service API usage
    boto_config = {
        "user_agent_extra": f"AwsSolution/{SOLUTION_ID}/{SOLUTION_VERSION}"
    }
    cf_client = boto3.client("cloudfront", config=config.Config(**boto_config))

    # Dissociate web acl resource before deleting web acl
    cf_distribution_id = event["ResourceProperties"]["CF_DISTRIBUTION_ID"]
    response = cf_client.get_distribution_config(Id=cf_distribution_id)

    cf_distribution_config = response["DistributionConfig"]
    cf_distribution_config["WebACLId"] = ""  # provide an empty web ACL ID

    _ = cf_client.update_distribution(
        DistributionConfig=cf_distribution_config,
        Id=cf_distribution_id,
        IfMatch=response["ETag"],  # rename the ETag field to IfMatch
    )

    # Delete Web ACL
    wafv2_client = boto3.client("wafv2", region_name="us-east-1")
    webacl_name = event["ResourceProperties"]["WAF_WEBACL_NAME"]
    webacl_id = event["ResourceProperties"]["WAF_WEBACL_ID"]
    webacl_locktoken = event["ResourceProperties"]["WAF_WEBACL_LOCKTOKEN"]

    _ = wafv2_client.delete_web_acl(
        Name=webacl_name, Scope="CLOUDFRONT", Id=webacl_id, LockToken=webacl_locktoken
    )

    logger.info(f"Deleted WAF WebAcl with name {webacl_name} and id {webacl_id}")

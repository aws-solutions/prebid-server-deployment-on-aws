# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_solutions.core.helpers import get_aws_region
import boto3

class ResourceLookup():
    def __init__(
            self, 
            logical_id,
            stack_name
            ):
        self.logical_id = logical_id
        self.stack_name = stack_name
        self.region = get_aws_region()
        self.cfn_client = boto3.client('cloudformation', region_name=self.region)
        self.physical_id = self.get_physical_id()

    def get_physical_id(self):
        response = self.cfn_client.describe_stack_resource(
            StackName=self.stack_name,
            LogicalResourceId=self.logical_id
        )
        return response['StackResourceDetail']['PhysicalResourceId']
    
    def get_arn(self, resource_type, account_id):
        arn_mapping = {
            "lambda": f"arn:aws:lambda:{self.region}:{account_id}:function:{self.physical_id}",
            "role": f"arn:aws:iam::{account_id}:role/{self.physical_id}"
        }

        return arn_mapping[resource_type]

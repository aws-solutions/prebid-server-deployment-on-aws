# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/custom_resources/delete_lambda_eni.
# USAGE:
#   ./run-unit-tests.sh --test-file-name custom_resources/test_delete_lambda_eni.py
###############################################################################

import boto3
from unittest.mock import patch
from moto import mock_aws


@patch("crhelper.CfnResource")
@patch("custom_resources.vpc_eni_lambda.delete_lambda_eni.helper")
def test_event_handler(helper_mock, _):
    from custom_resources.vpc_eni_lambda.delete_lambda_eni import event_handler

    event_handler({}, None)
    helper_mock.assert_called_once()


@mock_aws
@patch("crhelper.CfnResource")
def test_on_delete(_):
    ec2_client = boto3.client("ec2")
    ec2_resource = boto3.resource("ec2")
    vpc_resp = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
    subnet_resp = ec2_client.create_subnet(VpcId=vpc_resp["Vpc"]["VpcId"], CidrBlock="10.0.0.0/16")
    network_resp = ec2_client.create_network_interface(Groups=["test-123"], SubnetId=subnet_resp["Subnet"]["SubnetId"])
    instance_resp = ec2_resource.create_instances(ImageId="some-image", MinCount=1, MaxCount=1)
    ec2_client.attach_network_interface(NetworkInterfaceId=network_resp["NetworkInterface"]["NetworkInterfaceId"], InstanceId=instance_resp[0].id, DeviceIndex=0)

    from custom_resources.vpc_eni_lambda.delete_lambda_eni import on_delete

    with patch("custom_resources.vpc_eni_lambda.delete_lambda_eni.helper.Data", {}) as helper_update_mock:
        events = {
            "ResourceProperties": {
                "SECURITY_GROUP_ID": "test-123"
            }
        }
        on_delete(events, None)
        assert helper_update_mock["Response"] is not None
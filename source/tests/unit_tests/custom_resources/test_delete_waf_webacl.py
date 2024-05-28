# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/custom_resources/delete_waf_webacl.
# USAGE:
#   ./run-unit-tests.sh --test-file-name custom_resources/test_delete_waf_webacl.py
###############################################################################


from unittest.mock import patch


@patch("crhelper.CfnResource")
@patch("custom_resources.waf_webacl_lambda.delete_waf_webacl.helper")
def test_event_handler(helper_mock, _):
    from custom_resources.waf_webacl_lambda.delete_waf_webacl import event_handler

    event_handler({}, None)
    helper_mock.assert_called_once()


@patch("custom_resources.waf_webacl_lambda.delete_waf_webacl.boto3.client")
@patch("crhelper.CfnResource")
def test_on_delete(_, mock_boto3):
    event = {
        "ResourceProperties":
            {
                "CF_DISTRIBUTION_ID": "1234",
                "WAF_WEBACL_NAME": "test_name",
                "WAF_WEBACL_ID": 1234,
                "WAF_WEBACL_LOCKTOKEN": "lock_token",
            },
    }

    cf_resp = {
        "DistributionConfig": {
            "WebACLId": ""
        },
        "ETag": "testtag"
    }

    mock_boto3.return_value.get_distribution_config.return_value = cf_resp
    mock_boto3.return_value.update_distribution.return_value = None
    mock_boto3.return_value.delete_web_acl.return_value = None
    from custom_resources.waf_webacl_lambda.delete_waf_webacl import on_delete

    with patch("custom_resources.waf_webacl_lambda.delete_waf_webacl.helper.Data", {}):
        on_delete(event, None)
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/custom_resources/get_prefix_id.
# USAGE:
#   ./run-unit-tests.sh --test-file-name custom_resources/test_get_prefix_id.py
###############################################################################


from unittest.mock import patch
from moto import mock_aws


@patch("crhelper.CfnResource")
@patch("custom_resources.prefix_id_lambda.get_prefix_id.helper")
def test_event_handler(helper_mock, _):
    from custom_resources.prefix_id_lambda.get_prefix_id import event_handler

    event_handler({}, None)
    helper_mock.assert_called_once()


@mock_aws
@patch("crhelper.CfnResource")
def test_on_create(_):
    from custom_resources.prefix_id_lambda.get_prefix_id import on_create

    with patch("custom_resources.prefix_id_lambda.get_prefix_id.helper.Data", {}) as helper_update_mock:
        on_create({}, None)
        assert helper_update_mock["prefix_list_id"] is not None
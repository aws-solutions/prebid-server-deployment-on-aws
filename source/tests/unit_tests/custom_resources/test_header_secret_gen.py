# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/custom_resources/header_secret_gen.
# USAGE:
#   ./run-unit-tests.sh --test-file-name custom_resources/test_header_secret_gen.py
###############################################################################


from unittest.mock import patch


@patch("crhelper.CfnResource")
@patch("custom_resources.header_secret_lambda.header_secret_gen.helper")
def test_event_handler(helper_mock, _):
    from custom_resources.header_secret_lambda.header_secret_gen import event_handler

    event_handler({}, None)
    helper_mock.assert_called_once()


@patch("crhelper.CfnResource")
def test_on_create(_):
    from custom_resources.header_secret_lambda.header_secret_gen import on_create

    with patch("custom_resources.header_secret_lambda.header_secret_gen.helper.Data", {}) as helper_update_mock:
        on_create({}, None)
        assert helper_update_mock["header_secret_value"] is not None
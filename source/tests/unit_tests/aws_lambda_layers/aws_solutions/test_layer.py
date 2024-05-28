# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/aws_lambda_layers/aws_solutions/layer.py.
# USAGE:
#   ./run-unit-tests.sh --test-file-name aws_lambda_layers/aws_solutions/test_layer.py
###############################################################################


import uuid
from unittest.mock import MagicMock, patch
from unit_tests.test_commons import FakeClass


def test_solutions_layer():
    from aws_lambda_layers.aws_solutions.layer import SolutionsLayer

    with patch("aws_lambda_layers.aws_solutions.layer.super") as mock_super:
        mock_def = MagicMock()
        SolutionsLayer.__init__(self=mock_def, scope=FakeClass(), construct_id=str(uuid.uuid4()))
        mock_super.assert_called_once()

        node_mock_cls = MagicMock(node=MagicMock(try_find_child=MagicMock(return_value=True)))
        with patch("aws_cdk.Stack.of", return_value=node_mock_cls) as mock_cdk_stack_of:
            assert SolutionsLayer.get_or_create(self=mock_def, scope=mock_def, **{}) is True
            mock_cdk_stack_of.assert_called_once()
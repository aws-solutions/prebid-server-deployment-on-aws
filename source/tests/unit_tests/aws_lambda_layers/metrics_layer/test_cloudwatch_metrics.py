# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/aws_lambda_layers/metrics_layer/metrics/cloudwatch_metrics.
# USAGE:
#   ./run-unit-tests.sh --test-file-name aws_lambda_layers/metrics_layer/test_cloudwatch_metrics.py
###############################################################################


import boto3
import logging
from moto import mock_aws


logger = logging.getLogger()

@mock_aws
def test_metrics():
    from aws_lambda_layers.metrics_layer.python.cloudwatch_metrics.metrics import Metrics

    metrics_namespace = "test"
    resource_prefix = "test"
    metrics_cls = Metrics(metrics_namespace=metrics_namespace, resource_prefix=resource_prefix, logger=logger)
    assert metrics_namespace == metrics_cls.metrics_namespace
    assert resource_prefix == metrics_cls.resource_prefix
    assert logger == metrics_cls.logger

    metric_name = "test_metric"
    expected_dimension = [{'Name': 'stack-name', 'Value': resource_prefix}]
    metrics_cls.put_metrics_count_value_1(metric_name=metric_name)
    cw_client = boto3.client("cloudwatch")
    resp = cw_client.list_metrics(
        Namespace=metrics_namespace,
        MetricName=metric_name,
        Dimensions=expected_dimension
    )

    assert resp["Metrics"] == [
        {
            'Namespace': metrics_namespace,
            'MetricName': metric_name,
            'Dimensions': expected_dimension
        }
    ]
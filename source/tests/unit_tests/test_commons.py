# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
import logging
from functools import wraps
from unittest.mock import patch
from contextlib import ExitStack, contextmanager


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class FakeClass():
    def __init__(self) -> None:
        logger.debug("Fake init.")


def reload_module(module):
    module = importlib.import_module(module)
    importlib.reload(module)


aws_cdk_services = [
    "aws_cdk.Stack.of",
    "aws_cdk.aws_datasync",
    "aws_solutions.cdk.aws_lambda.python.function.SolutionsPythonFunction",
    "aws_cdk.CustomResource",
    "aws_cdk.aws_iam",
    "aws_cdk.aws_ec2",
    "aws_cdk.aws_efs",
    "aws_cdk.aws_ecs_patterns",
    "aws_cdk.aws_elasticloadbalancingv2",
    "aws_cdk.aws_cloudfront",
    "aws_cdk.aws_cloudfront_origins",
    "aws_cdk.aws_s3",
    "aws_cdk.aws_kms",
    "aws_cdk.CfnResource",
    "aws_cdk.CfnOutput",         
    "aws_cdk.aws_ecs",
    "aws_cdk.aws_events",
    "aws_cdk.aws_events_targets",
    "aws_cdk.aws_lambda_event_sources",
    "aws_cdk.aws_lambda.FileSystem",
    "aws_cdk.aws_cloudtrail",
    "aws_cdk.aws_glue",
    "aws_cdk.aws_lambda.LayerVersion"
]

@contextmanager
def handle_contexts(patched_services):
    with ExitStack() as exit_stack:
        yield [ exit_stack.enter_context(patch_service) for patch_service in patched_services]


def mocked_common_services(**test_kwargs):
    
    def mocked_services_decorator(test_func):
        @wraps(test_func)
        def wrapper(*args, **kwargs):
            mock_services = [*test_kwargs.get("override_aws_cdk_services", aws_cdk_services), *test_kwargs.get("add_patch", [])]
            patched_services = tuple(list([ patch(mock_service) for mock_service in mock_services]))
            with handle_contexts(patched_services) as services:
                test_func(*args, **kwargs)
                for service in services:
                    try:
                        service.assert_called()
                    except AssertionError as assertionExcption:
                        if test_kwargs.get("validate_mocks"):
                            raise
                        logger.warning(assertionExcption)
                    services[service].reset_mock()
        return wrapper
    return mocked_services_decorator
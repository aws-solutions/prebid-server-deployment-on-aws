# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/prebid_server/prebid_server_stack.py.
# USAGE:
#   ./run-unit-tests.sh --test-file-name prebid_server/test_prebid_server_stack.py
###############################################################################


import os
import uuid
import pytest
from unittest.mock import MagicMock
from unit_tests.test_commons import mocked_common_services, reload_module, FakeClass


add_patch = [
    "prebid_server.prebid_datasync_constructs.EfsCleanup",
    "prebid_server.prebid_datasync_constructs.DataSyncTask",
    "prebid_server.prebid_datasync_constructs.DataSyncMonitoring",
    "prebid_server.cloudwatch_alarms_construct.CloudwatchAlarms",
    "prebid_server.alb_access_logs_construct.AlbAccessLogsConstruct",
    "prebid_server.cloudtrail_construct.CloudTrailConstruct",
    "prebid_server.prebid_glue_constructs.GlueEtl",
    "prebid_server.prebid_artifacts_constructs.ArtifactsManager",
    "prebid_server.cloudwatch_metrics_construct.CloudwatchMetricsConstruct",
    "prebid_server.operational_metrics_construct.OperationalMetricsConstruct",
    "prebid_server.prebid_server_stack.super",
]

@pytest.fixture
def apply_env():
    os.environ['PUBLIC_ECR_REGISTRY'] = "test.ecr.aws/123456"
    os.environ['ECR_REPO_NAME'] = "test-prebid-server"
    os.environ['PUBLIC_ECR_TAG'] = "v0.0.1-test"

@mocked_common_services(
    add_patch=[
        "aws_cdk.aws_ecr_assets.DockerImageAsset",
        *add_patch
    ],
)
def test_prebid_server_stack_from_docker_image_asset(apply_env):

    mock_def = MagicMock(bucket_name="s3-bucket", node=MagicMock(try_get_context=MagicMock(return_value="12345"), try_find_child=MagicMock(return_value=True)))
    reload_module("prebid_server.prebid_server_stack")
    from prebid_server.prebid_server_stack import PrebidServerStack

    PrebidServerStack.__init__(self=mock_def, scope=FakeClass(), construct_id=str(uuid.uuid4()), **{})
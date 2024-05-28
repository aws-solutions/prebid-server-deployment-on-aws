# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/app.py.
# USAGE:
#   ./run-unit-tests.sh --test-file-name test_app.py
###############################################################################

import os.path
import shutil
import sys
from unittest.mock import patch
from unit_tests.test_commons import mocked_common_services

import pytest


@pytest.fixture
def build_app_fix():
    solution_helper_build_path = "../source/cdk_solution_helper_py/helpers_common/build"
    if os.path.isdir(solution_helper_build_path):
        try:
            shutil.rmtree(solution_helper_build_path)
        except OSError:
            pass

    sys.path.insert(0, "./infrastructure")

    with patch("app.__name__", "__main__"):
        from app import build_app
        return build_app()


@mocked_common_services(
    add_patch=[
        "aws_cdk.App",
        "aws_cdk.aws_ecr_assets.DockerImageAsset",
        "prebid_server.prebid_datasync_constructs.EfsLocation",
        "prebid_server.prebid_datasync_constructs.S3Location",
        "prebid_server.prebid_datasync_constructs.EfsCleanup",
        "prebid_server.cloudtrail_construct.CloudTrailConstruct",
        "prebid_server.prebid_server_stack.PrebidServerStack",
        "prebid_server.prebid_glue_constructs.GlueEtl",
        "prebid_server.prebid_artifacts_constructs.ArtifactsManager",
        "prebid_server.cloudwatch_metrics_construct.CloudwatchMetricsConstruct",
        "prebid_server.operational_metrics_construct.OperationalMetricsConstruct",
    ]
)
def test_build_app(build_app_fix):
    app_stack = build_app_fix.get_stack_by_name("prebid-server-deployment-on-aws")
    assert app_stack is not None
    assert app_stack.stack_name == "prebid-server-deployment-on-aws"
    assert app_stack.template is not None
    assert app_stack.template["Description"] == "(SO9999test) - Prebid Server Deployment on AWS. Version v99.99.99"
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/prebid_server/prebid_glue_constructs.py.
# USAGE:
#   ./run-unit-tests.sh --test-file-name prebid_server/test_prebid_glue_constructs.py
###############################################################################

import uuid
from unittest.mock import MagicMock
from unit_tests.test_commons import mocked_common_services, FakeClass, reload_module



@mocked_common_services(
    add_patch=[
        "prebid_server.prebid_artifacts_constructs.ArtifactsManager",
        "prebid_server.prebid_glue_constructs.super",
    ]
)
def test_glue_etl():
    mock_src_bucket = MagicMock(bucket_arn="test_arn/source_bucket")
    mock_artifcact_bucket = MagicMock(bucket_arn="test_arn/artifactbucket")
    mock_def = MagicMock(artifacts_bucket=mock_artifcact_bucket, source_bucket=mock_src_bucket)
    mock_task = MagicMock(attr_task_arn="task-arn")
    reload_module("prebid_server.prebid_glue_constructs")
    from prebid_server.prebid_glue_constructs import GlueEtl
    
    GlueEtl.__init__(
        self=mock_def,
        scope=FakeClass(),
        id=str(uuid.uuid4()),
        artifacts_construct=MagicMock(bucket=mock_artifcact_bucket),
        script_file_name="filename",
        source_bucket=mock_src_bucket,
        datasync_task=mock_task
    )
    
    GlueEtl._create_output_bucket(self=mock_def)
    GlueEtl._create_glue_database(self=mock_def)
    GlueEtl._create_glue_job(self=mock_def)
    GlueEtl._create_glue_job_trigger(self=mock_def)

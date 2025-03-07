# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

TEST_REGIONS = ["us-east-1"]
SKIP_REASON=f"Test ETL metrics for only these regions: {TEST_REGIONS}"


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
#!/usr/bin/env bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------
# PURPOSE:
# This entrypoint script is used to start the Prebid Server container.
#
# An environment variable named ECS_CONTAINER_METADATA_URI_V4
# is injected by ECS into each container. The variable contains a URI that
# is used to retrieve container status and data.
#
# See:
# https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-metadata-endpoint-v4.html    
#
# The entrypoint defined below retrieves the data and parses the
# container's unique ID from it and uses the ID to ensure
# log data is written to a unique directory under /mnt/efs/.
# The container ID is also included with logs sent directly
# to CloudWatch.
#
# If the environment variable ECS_CONTAINER_METADATA_URI_V4 is not set,
# the string "default-container-id" is returned instead so that the
# container can be run locally.
#
# Metrics are sent to /mnt/efs/metrics folder also using the container ID
# in the path. Files have the name prebid-metrics.log.
#
# The default Java executable entry point specified in this script can be
# customized or replaced with a different command or executable.
# ------------------------------------------------------------------------------

PREBID_CONFIGS_DIR="/prebid-configs"

/usr/bin/java \
    -DcontainerId=$(if [ -z "$ECS_CONTAINER_METADATA_URI_V4" ]; then echo "default-container-id"; else curl -s "${ECS_CONTAINER_METADATA_URI_V4}/task" | jq -r '.Containers[0].DockerId' 2>/dev/null | cut -d'-' -f1 || echo "default-container-id"; fi) \
    -Dlogging.config=${PREBID_CONFIGS_DIR}/prebid-logging.xml \
    -XX:+UseParallelGC \
    -jar target/prebid-server.jar \
    --spring.config.additional-location=${PREBID_CONFIGS_DIR}/prebid-config.yaml

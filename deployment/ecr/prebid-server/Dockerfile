# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# Setup environment for building prebid-server-java
RUN yum -y install maven-amazon-corretto17

# Remove python setuptools and package installer
RUN yum -y remove python-setuptools
RUN yum -y remove python-pip 

RUN yum -y install git
RUN yum -y install jq
RUN git clone https://github.com/prebid/prebid-server-java.git
COPY config.json prebid-server-java/
COPY prebid-logging.xml prebid-server-java/
COPY prebid-server-java-patches.diff prebid-server-java/
WORKDIR /prebid-server-java

# Download the user-specified version of prebid-server-java
RUN git fetch origin --tags
RUN git checkout $(jq -r .GIT_TAG_VERSION config.json)
RUN git apply prebid-server-java-patches.diff

# Build prebid-server-java using Maven
RUN mvn clean package $(jq -r .MVN_CLI_OPTIONS config.json)

# Remove the local Maven repository
RUN rm -rf /root/.m2

EXPOSE 8080
EXPOSE 8060

# An environment variable named ECS_CONTAINER_METADATA_URI_V4
# is injected by AWS Fargate into each container in a task.
# The entrypoint defined below parses the container's unique
# ID from that environment variable and uses it to ensure the
# prebid-server.log is written to a unique directory under
# /mnt/efs/.
#
# Metrics are sent to /mnt/efs/metrics folder also using the
# container ID in the path. Files have the name prebid-metrics.log.
#
# The space that is prepended to ${ECS_CONTAINER_METADATA_URI_V4})
# is needed so that the container can be built locally where that
# environment variable is not defined.
ENTRYPOINT /usr/bin/java \
    -DcontainerId=$(basename " "${ECS_CONTAINER_METADATA_URI_V4}) \
    -Dlogging.config=./prebid-logging.xml \
    -XX:+UseParallelGC \
    -jar target/prebid-server.jar \
    --spring.config.additional-location=sample/prebid-config.yaml
    

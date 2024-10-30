# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


# ------------------------------------------------------------------------------------------------------------------------------------------------------
# PURPOSE:
#  This Dockerfile is designed to build a Docker image for the Prebid Server Java application by cloning the repository,
#  building the application using Maven, and setting up the necessary configuration and scripts to run the application inside the container on aws.
# -------------------------------------------------------------------------------------------------------------------------------------------------------
# USAGE:
#  For instructions on how to build this Dockerfile locally, please refer to the README.md file in the current directory.
# -------------------------------------------------------------------------------------------------------------------------------------------------------


FROM public.ecr.aws/docker/library/maven:3-amazoncorretto-21-al2023

# Install required packages
RUN yum -y install git jq aws-cli

# Update Python packages to address security vulnerabilities
RUN dnf update python-setuptools --releasever 2023.1.20230719
RUN dnf update python-pip --releasever 2023.3.20231211

# Clone the Prebid Server Java repository
RUN git clone --single-branch --branch master https://github.com/prebid/prebid-server-java.git

# Copy source build configuration file
COPY docker-build-config.json docker-build-config.json

# Set the working directory to the cloned repository
WORKDIR /prebid-server-java

# Fetch tags and checkout the specified version
RUN git fetch origin --tags
RUN git checkout $(jq -r .GIT_TAG_VERSION ../docker-build-config.json)

# Build the Prebid Server Java application using Maven
RUN mvn clean package $(jq -r .MVN_CLI_OPTIONS ../docker-build-config.json)

# Remove the local Maven repository to reduce image size
RUN rm -rf /root/.m2

# Expose ports for the Prebid Server Java application
EXPOSE 8080 8060

# Copy the bootstrap script
COPY bootstrap.sh ../bootstrap.sh

# Set the entrypoint to execute the bootstrap script
ENTRYPOINT ["sh", "../bootstrap.sh"]

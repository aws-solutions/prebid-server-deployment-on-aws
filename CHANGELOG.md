# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2025-03-07

- Upgrade to Prebid Server v3.22 and underlying Docker base image
- Optimized container image using jlink reducing image size from 774 MB to 142 MB
- Change to Poetry for Python dependency management
- Add script to run Prebid Server container locally with stack settings

## [1.1.0] - 2024-10-31

- Upgrade to Prebid Server v3.13 and underlying Docker base image
- ECS runtime logs in AWS CloudWatch instead of S3
- Option to opt-out of installing CloudFront and WAF
- Customize Prebid Server configuration through files in S3
- Option to specify a custom container image

## [1.0.2] - 2024-09-23

- Upgrade Python `requests` package to version 2.32.3 in requirements.txt
- Bug fix for launch failure of EfsCleanupContainerStop Lambda function

## [1.0.1] - 2024-08-02

- Remove python `setuptools` and `pip` from prebid server docker image
- Include missing copyright header for `source/infrastructure/prebid_server/stack_constants.py`

## [1.0.0] - 2024-05-28

### Added

- All files, initial version

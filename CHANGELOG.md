# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-05-28

### Added

- All files, initial version

## [1.0.1] - 2024-08-02

- Remove python `setuptools` and `pip` from prebid server docker image
- Include missing copyright header for `source/infrastructure/prebid_server/stack_constants.py`


## [1.0.2] - 2024-09-20

- Upgrade Python `requests` package to version 2.32.3 in requirements.txt
- Bug fix for launch failure of EfsCleanupContainerStop Lambda function

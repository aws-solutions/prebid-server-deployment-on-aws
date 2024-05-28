# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import re
from pathlib import Path

import setuptools

VERSION_RE = re.compile(r"\#\# \[(?P<version>.*)\]", re.MULTILINE)  # NOSONAR


def get_version():
    """
    Detect the solution version from the changelog. Latest version on top.
    """
    changelog = open(Path(__file__).resolve().parent.parent / "CHANGELOG.md").read()
    versions = VERSION_RE.findall(changelog)
    if not len(versions):
        raise ValueError("use the standard semver format in your CHANGELOG.md")
    build_version = versions[0]
    print(f"Build Version: {build_version}")
    return build_version


setuptools.setup(
    name="aws-solutions-cdk",
    version=get_version(),
    description="Tools to make AWS Solutions deployments with CDK + Python more manageable",
    long_description=open("../README.md").read(),
    author="Amazon Web Services",
    url="https://aws.amazon.com/solutions/implementations",
    license="Apache License 2.0",
    packages=setuptools.find_namespace_packages(),
    package_data={
        "": [
            "requirements.txt",
            "Dockerfile",
            "__aws_solutions_bundling_version__",
        ]
    },
    install_requires=[
        "pip>=21.3",
        "aws_cdk_lib>=2.7.0",
        "Click>=7.1.2",
        "boto3>=1.17.52",
        "requests>=2.31.0",
        "crhelper>=2.0.6",
    ],
    entry_points="""
        [console_scripts]
        build-s3-cdk-dist=aws_solutions.cdk.scripts.build_s3_cdk_dist:cli
    """,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
    zip_safe=False,
)
